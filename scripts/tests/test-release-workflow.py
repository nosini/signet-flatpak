#!/usr/bin/env python3
"""Exercise the workflow's cache, publication gates and release commands offline."""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from types import SimpleNamespace as Namespace
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = yaml.safe_load((ROOT / ".github/workflows/flatpak.yml").read_text())


def condition(expression, **context):
    """Evaluate the boolean expressions used by this workflow's gates."""
    expression = expression.strip().removeprefix("${{").removesuffix("}}")
    expression = " ".join(expression.split()).replace("&&", " and ").replace("||", " or ")
    expression = re.sub(r"!(?!=)", "not ", expression)
    return eval(expression, {"__builtins__": {}}, dict(
        context, startsWith=lambda text, prefix: text.startswith(prefix),
    ))


class ReleaseWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.directory = Path(self.scratch.name)
        self.env = dict(os.environ, APP_NAME="Example", TAG="v1.2.3")

    def run_step(self, job, name, **env):
        step = next(step for step in WORKFLOW["jobs"][job]["steps"]
                    if step.get("name") == name)
        return subprocess.run(
            ["bash", "-e", "-o", "pipefail", "-c", step["run"]],
            cwd=self.directory, env=dict(self.env, **env),
            capture_output=True, text=True,
        )

    def test_tag_builds_keep_checks_and_use_event_commit(self):
        self.assertEqual(set(WORKFLOW[True]), {"push", "pull_request", "workflow_dispatch"})
        self.assertEqual(WORKFLOW[True]["push"], {"tags": ["v*"]})
        checks = yaml.safe_load((ROOT / ".github/workflows/checks.yml").read_text())
        self.assertEqual(checks[True]["push"], {"branches": ["main"]})
        for name in ("setup", "build", "publish"):
            checkout = next(step for step in WORKFLOW["jobs"][name]["steps"]
                            if step.get("uses", "").startswith("actions/checkout@"))
            self.assertEqual(checkout["with"]["ref"], "${{ github.sha }}")

    def test_tag_classification(self):
        for tag, stable in (
            ("v0.1.4", True), ("v0.1.4-1", True),
            ("v0.1.4-12", True), ("v0.1.5-rc1", False),
            ("v0.1.5-beta.2", False), ("v0.1.5rc1", False),
            ("v0.1.4-", False), ("v0.1.4-1rc1", False),
        ):
            with self.subTest(tag=tag):
                output = self.directory / "output"
                result = self.run_step(
                    "setup", "Classify the release tag",
                    TAG=tag, GITHUB_OUTPUT=str(output),
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(output.read_text(), f"stable={str(stable).lower()}\n")
                output.unlink()

    def test_publication_requires_stable_tag_push_or_manual_main(self):
        expression = next(step for step in WORKFLOW["jobs"]["setup"]["steps"]
                          if step.get("id") == "arches")["env"]["PUBLISH"]
        for event, ref, stable, enabled, expected in (
            ("push", "refs/tags/v0.1.4", "true", "true", True),
            ("push", "refs/tags/v0.1.5-rc1", "false", "true", False),
            ("push", "refs/tags/v0.1.4", "true", "false", False),
            ("push", "refs/heads/main", "true", "true", False),
            ("pull_request", "refs/pull/1/merge", "", "true", False),
            ("workflow_dispatch", "refs/heads/main", "", "true", True),
            ("workflow_dispatch", "refs/heads/main", "", "false", False),
            ("workflow_dispatch", "refs/heads/update/upstream", "", "true", False),
            ("workflow_dispatch", "refs/tags/v0.1.4", "true", "true", False),
        ):
            for cache_only in (False, True):
                with self.subTest(event=event, ref=ref, enabled=enabled, cache_only=cache_only):
                    self.assertEqual(condition(
                        expression, github=Namespace(event_name=event, ref=ref),
                        vars=Namespace(PUBLISH_FLATPAK=enabled),
                        inputs=Namespace(cache_only=cache_only),
                        steps=Namespace(release=Namespace(outputs=Namespace(stable=stable))),
                    ), expected and not cache_only)

    def test_cache_only_is_an_optional_boolean(self):
        option = WORKFLOW[True]["workflow_dispatch"]["inputs"]["cache_only"]
        self.assertEqual(option["type"], "boolean")
        self.assertIs(option["default"], False)
        self.assertFalse(option.get("required", False))

    def test_cache_snapshots_are_isolated_and_saved_after_validation(self):
        steps = WORKFLOW["jobs"]["build"]["steps"]
        restore = next(step for step in steps if step.get("id") == "build-cache")
        save = next(step for step in steps if step.get("uses") == "actions/cache/save@v6")
        builder = next(step for step in steps if step.get("uses", "").startswith(
            "flatpak/flatpak-github-actions/flatpak-builder@"))
        self.assertEqual(restore["uses"], "actions/cache/restore@v6")
        self.assertEqual(restore["with"]["path"], ".flatpak-builder")
        self.assertEqual(save["with"]["path"], restore["with"]["path"])
        self.assertEqual(save["with"]["key"], "${{ steps.build-cache.outputs.cache-primary-key }}")
        prefix = restore["with"]["restore-keys"].strip()
        self.assertEqual(len(prefix.splitlines()), 1)
        for part in ("${{ runner.os }}", "${{ matrix.arch }}", "${{ env.APP_ID }}",
                     "${{ env.FLATPAK_BRANCH }}", "${{ hashFiles('.github/workflows/flatpak.yml') }}"):
            self.assertIn(part, prefix)
        self.assertEqual(restore["with"]["key"],
                         prefix + "${{ github.run_id }}-${{ github.run_attempt }}")
        self.assertIs(builder["with"]["cache"], True)
        self.assertIs(builder["with"]["restore-cache"], False)
        self.assertIs(builder["with"]["save-cache"], False)
        self.assertEqual(builder["with"]["state-dir"], restore["with"]["path"])
        self.assertLess(steps.index(restore), steps.index(builder))
        for name in ("Lint the exported build", "Check the installed app against its runtime"):
            check = next(step for step in steps if step.get("name") == name)
            self.assertLess(steps.index(builder), steps.index(check))
            self.assertLess(steps.index(check), steps.index(save))
            self.assertFalse(check.get("continue-on-error", False))
        self.assertNotIn("if", save)
        self.assertFalse(save.get("continue-on-error", False))

    def test_release_waits_for_validation_and_required_deployment(self):
        job = WORKFLOW["jobs"]["release"]
        self.assertEqual(set(job["needs"]), {"setup", "build", "publish", "deploy"})
        self.assertEqual(job["permissions"], {"contents": "write"})
        self.assertEqual(job["env"]["GH_TOKEN"], "${{ github.token }}")
        cases = [
            ({}, True),
            ({"publish_enabled": "false", "publish": "skipped", "deploy": "skipped"}, True),
            ({"publish_enabled": "false"}, False),
            ({"publish": "skipped", "deploy": "skipped"}, False),
            ({"event": "workflow_dispatch"}, False),
            ({"event": "pull_request"}, False),
            ({"ref": "refs/heads/main"}, False),
            ({"cancelled": True}, False),
        ]
        for name in job["needs"]:
            for state in ("failure", "cancelled", "skipped"):
                cases.append(({name: state}, False))
        for overrides, expected in cases:
            values = dict(event="push", ref="refs/tags/v0.1.4", cancelled=False,
                          publish_enabled="true", setup="success", build="success",
                          publish="success", deploy="success")
            values.update(overrides)
            needs = Namespace(**{name: Namespace(result=values[name]) for name in job["needs"]})
            needs.setup.outputs = Namespace(publish=values["publish_enabled"])
            for cache_only in (False, True):
                with self.subTest(overrides=overrides, cache_only=cache_only):
                    self.assertEqual(condition(
                        job["if"], github=Namespace(event_name=values["event"], ref=values["ref"]),
                        inputs=Namespace(cache_only=cache_only),
                        needs=needs, cancelled=lambda: values["cancelled"],
                    ), expected and not cache_only)

    def release_commands(self, *, stable="true", exists="false", fail="false"):
        bundles = self.directory / "bundles"
        bundles.mkdir()
        for name in ("signet-x86_64.flatpak", "signet-aarch64.flatpak"):
            (bundles / name).touch()
        binary = self.directory / "gh"
        binary.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, sys\n"
            "args = sys.argv[1:]\n"
            "if args[:2] == ['release', 'view']:\n"
            "    sys.exit(0 if os.environ['RELEASE_EXISTS'] == 'true' else 1)\n"
            "with open(os.environ['GH_LOG'], 'a') as log:\n"
            "    log.write(json.dumps(args) + '\\n')\n"
            "sys.exit(1 if os.environ['RELEASE_FAIL'] == 'true' else 0)\n"
        )
        binary.chmod(0o755)
        log = self.directory / "gh.jsonl"
        result = self.run_step(
            "release", "Create the release and upload the tested bundles",
            PATH=f"{self.directory}:{os.environ['PATH']}", STABLE=stable,
            RELEASE_EXISTS=exists, RELEASE_FAIL=fail, GH_LOG=str(log),
        )
        commands = [json.loads(line) for line in log.read_text().splitlines()]
        return result, commands

    def test_stable_release_includes_both_arches_and_verifies_tag(self):
        result, commands = self.release_commands()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(commands), 1)
        args = commands[0]
        self.assertEqual(args[:3], ["release", "create", "v1.2.3"])
        self.assertIn("--verify-tag", args)
        self.assertIn("--generate-notes", args)
        self.assertIn("bundles/signet-x86_64.flatpak", args)
        self.assertIn("bundles/signet-aarch64.flatpak", args)
        self.assertNotIn("--prerelease", args)

    def test_prerelease_cannot_become_latest(self):
        result, commands = self.release_commands(stable="false")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--prerelease", commands[0])
        self.assertIn("--latest=false", commands[0])

    def test_retry_uploads_to_existing_release(self):
        result, commands = self.release_commands(exists="true")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(commands), 1)
        self.assertEqual(commands[0][:3], ["release", "upload", "v1.2.3"])
        self.assertIn("--clobber", commands[0])

    def test_retry_keeps_existing_prerelease_out_of_latest(self):
        result, commands = self.release_commands(stable="false", exists="true")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(commands[0], ["release", "edit", "v1.2.3", "--prerelease", "--latest=false"])
        self.assertEqual(commands[1][:3], ["release", "upload", "v1.2.3"])
        self.assertIn("--clobber", commands[1])

    def test_upload_failure_fails_the_step(self):
        result, _ = self.release_commands(exists="true", fail="true")
        self.assertNotEqual(result.returncode, 0)

    def test_creation_failure_fails_the_step(self):
        result, _ = self.release_commands(fail="true")
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
