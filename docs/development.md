# Development

## Layout

The manifest `eu.nosini.Signet.yml` builds the Linux workspace using GNOME
51 and the Rust and LLVM 22 SDK extensions. GnuPG, pinentry, curl, OpenSSL,
GTK and libadwaita come from the runtime. `cargo-sources.json` pins the
crates from Signet's Cargo.lock for an offline build, including the patched
KeePass crate already included in the upstream source.

The desktop file starts `launcher/signet-launch`, which prepares shared
runtime directories before starting the GUI. The package installs both
`signet-gui` and the `signet` CLI. Software-center metadata stays beside the
manifest so the update checker can edit release entries. The icon comes
from the upstream source. Crate license files and the upstream third-party notices
are installed under share/licenses. No source patches are applied.

`tests/check-installed.sh` checks the binaries, runtime tools, metadata,
license and GnuPG runtime socket selection inside the installed app.
`scripts/test-installed.sh` installs an exported local repository and runs
those checks. The other scripts and workflows come from
[flatpak-template](https://github.com/nosini/flatpak-template).

## Building

Install the builder, SDK and toolchains:

```sh
flatpak install --user flathub org.flatpak.Builder org.gnome.Sdk//51 \
  org.gnome.Platform//51 org.freedesktop.Sdk.Extension.rust-stable//26.08 \
  org.freedesktop.Sdk.Extension.llvm22//26.08
flatpak run org.flatpak.Builder --user --install-deps-from=flathub \
  --default-branch=stable --force-clean --repo=repo build-dir eu.nosini.Signet.yml
bash scripts/test-installed.sh
```

The manifest pins a published stable release by `tag` and exact `commit`,
and the metainfo screenshot uses the same tag. When moving to a new release,
update all three and regenerate the Cargo sources from that revision.
Publication is refused when the manifest has no release tag.

To build a local Linux checkout before its revision is published, generate
an ignored manifest beside the main one:

```sh
python3 scripts/local-manifest.py ../linux local-build.yml
flatpak run org.flatpak.Builder --user --install-deps-from=flathub \
  --default-branch=stable --force-clean --repo=repo build-dir local-build.yml
bash scripts/test-installed.sh
```

Regenerate Cargo sources first if that checkout has a different lock file.
The local manifest excludes its Git metadata and build output, and keeps
all packaging assets and pinned dependency sources. It is for development;
CI builds the main manifest.

The installed-app script refuses to replace an existing installation. It
adds a `local-test` remote for `repo/` and refreshes its summary. Remove the
test app and remote when finished:

```sh
flatpak --user uninstall eu.nosini.Signet
flatpak --user remote-delete local-test
```

To make an installable bundle:

```sh
flatpak build-bundle --runtime-repo=https://dl.flathub.org/repo/flathub.flatpakrepo \
  repo signet.flatpak eu.nosini.Signet stable
flatpak install --user signet.flatpak
```

## Cargo sources

Use the lock file from the exact packaged source revision. The generator
needs Python 3 with aiohttp and tomlkit. Install those with your system's
package manager, then run:

```sh
bash scripts/generate-cargo-deps.sh ../linux/Cargo.lock
```

`scripts/builder-tools.sh` fetches flatpak-builder-tools at a pinned commit.
The [Cargo generator](https://github.com/flatpak/flatpak-builder-tools/tree/master/cargo)
writes source archives, checksums and a Cargo source replacement config.
The build sets `CARGO_HOME=/run/build/signet/cargo` and runs Cargo with
`--locked --offline`; build commands have no network access. LLVM supplies
libclang for the OpenSSL bindings. Keep both SDK extension versions aligned
with the Freedesktop runtime underlying GNOME.

## Permissions and host integration

Window rendering uses Wayland, fallback X11, IPC and DRI. WebDAV uses the
network and the desktop Secret Service. File import and export use GTK's
file chooser portal, and startup uses the Background portal. No home or
host filesystem permission is granted.

`xdg-run/gnupg:create` shares GnuPG's socket directory, and
`xdg-run/signet:create` shares the agent control directory. Configuration
and vault storage remain private to the Flatpak. Host GnuPG reaches Signet
by using the absolute GNUPGHOME assignment copied from the GUI; this points
inside the app's persistent data directory. Both GnuPG implementations must
resolve that home to the same runtime socket. Host requests can have an
unidentified caller because the sandbox has a separate process namespace;
Signet then asks each time and does not cache approvals.

Check host integration with throwaway keys: create a vault, import a key,
copy GNUPGHOME into a host shell, sign and verify a file, and exercise both
approval and denial. Also check hidden-window prompts, file chooser access,
WebDAV password storage and login startup on a desktop with portals. Do not
run a native Signet service at the same time.

For the packaged CLI:

```sh
flatpak run --command=signet eu.nosini.Signet status
flatpak run --command=signet eu.nosini.Signet lock
```

## Checking

```sh
alias lint='flatpak run --command=flatpak-builder-lint org.flatpak.Builder'
lint --exceptions --user-exceptions lint-exceptions.json manifest eu.nosini.Signet.yml
lint appstream eu.nosini.Signet.metainfo.xml
lint --exceptions --user-exceptions lint-exceptions.json repo repo
shellcheck scripts/*.sh scripts/tests/*.sh tests/check-installed.sh launcher/signet-launch
actionlint
python3 scripts/tests/test-release-workflow.py
bash scripts/tests/test-update-upstream.sh
bash scripts/tests/test-prepare-repository.sh
```

The local exceptions cover only the app-ID domain's missing website and
screenshots hosted outside Flathub. Never submit the package or exception
requests to Flathub.

A shell against the installed app's Platform runtime:

```sh
flatpak run --command=sh eu.nosini.Signet
```

Add `--devel` to use the SDK for debugging. Bus access can be inspected with
`flatpak run --log-session-bus eu.nosini.Signet`. Portal grants can be listed
with `flatpak permission-show eu.nosini.Signet` and cleared with
`flatpak permission-reset eu.nosini.Signet`.

## CI and publication

The Flatpak workflow runs when a tag starting with `v` is pushed, for pull
requests and on manual runs. Pushes to main run the Checks workflow
without building the app. The Flatpak workflow lints, builds, exports and
tests x86_64 and aarch64 on GNOME 51 CI images. It uploads an unsigned
bundle for each architecture.
The Checks workflow lints the scripts and workflows, parses metadata and
runs the shared update and publishing script tests. Native debug information
is exported as `eu.nosini.Signet.Debug`; list it, and any automatically
exported Locale ref, when adding the app to the shared remote's registry.

CI restores `.flatpak-builder`, including downloaded sources, completed
module results and the C/C++ compiler cache. Flatpak checks the build inputs
and rebuilds affected modules when sources, dependencies, patches or the SDK
change. Lint and installed-app checks run every time; the cache is saved
only after they pass.

Each run saves a fresh snapshot, separated by app ID, architecture, Flatpak
branch and build workflow version, which includes the CI container image.
The next run restores the newest compatible snapshot. To start a new cache
namespace, bump `flatpak-v1` in both the key and restore prefix in the
workflow. Cache misses build normally.

GitHub lets tags and pull requests restore the default branch's cache,
but caches from one tag cannot be restored by another tag. To warm the
shared cache without publishing or creating a release, run the Flatpak
workflow on `main` with **cache_only** selected, or run this from the
packaging checkout:

```sh
gh workflow run flatpak.yml --ref main -f cache_only=true
```

Refresh it before releases when needed. GitHub removes caches unused for
more than seven days and evicts older entries when the repository's storage
limit is reached; see its [cache access and retention rules](https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching).

With `PUBLISH_FLATPAK=true`, pushing a stable version tag builds and
publishes the signed Flatpak repository from the tagged commit. Manual
Flatpak runs on main without `cache_only` also publish, so packaging fixes
can be shipped without a new tag.
Pull request builds, prerelease builds and manual runs on other refs produce
unsigned bundle artifacts only. Its separate publishing job
signs tested builds, preserves five previous commits, generates static
deltas, signs the software catalog and summary, and verifies those
signatures before deploying to GitHub Pages. The signing key never enters
the build job. Set Pages to GitHub Actions, store an ASCII-armored private
Flatpak signing key without a passphrase in `FLATPAK_GPG_PRIVATE_KEY`, and
then enable the variable. Generate and retain the key on your own machine;
keep a backup, since replacing it breaks installed clients' trust.

If the `github-pages` environment restricts deployment branches and tags,
allow the packaging tags with a Tag rule such as `v*`, and retain the main
Branch rule for manual publication. Then push a tag pointing to the
packaging commit to build, or run the Flatpak workflow manually on main.
The manifest's upstream Signet release pin is separate from this packaging
tag and must remain a stable release.

Stable tags have the form `v0.1.4`. A numeric suffix such as `v0.1.4-1`
identifies a stable packaging revision of the same upstream version. Other
suffixes, such as `v0.1.5-rc1`, build without replacing the stable Flatpak
repository and create GitHub prereleases that cannot become the latest
stable release. Use a new tag for each packaging revision; keep published
tags unchanged.

After a tag build passes validation and any required Pages deployment
succeeds, the workflow creates the GitHub Release automatically using the
runner's `GITHUB_TOKEN` and attaches the tested x86_64 and aarch64 `.flatpak`
bundles. Rerunning the tag build replaces assets on an existing release.
With `PUBLISH_FLATPAK` disabled, tag builds still create releases with
unsigned bundles. Manual builds do not create releases. No manual GitHub
Release creation or separate authenticated GitHub session is needed.

The repository URL defaults to
`https://nosini.github.io/signet-flatpak/`; `FLATPAK_REPO_URL` overrides it.
The publish job writes `signet.flatpakref` and `signet.flatpakrepo` with the
public key embedded. After publication, install using the signed reference:

```sh
flatpak install --user https://nosini.github.io/signet-flatpak/signet.flatpakref
```

After the first publication, add the package's app and extension refs to
[flatpak-repo](https://github.com/nosini/flatpak-repo)'s `apps.json`.

## Updating

The weekly Update workflow follows stable `vMAJOR.MINOR.PATCH` tags with
flatpak-external-data-checker. It proposes new source pins and metainfo
releases on `update/upstream`, then starts the build. If Cargo.lock changes,
regenerate cargo-sources.json from the new revision on that branch. Check
any changed assets and update the screenshot URL to the packaged tag.

Updates are reviewed by default. `AUTO_MERGE_UPDATES=true` enables merging
a successful automated update; changes made by people on the pending branch
keep it under manual review. Merging an update does not publish it or start
another build on main. Push a tag at the merged packaging commit to build
and ship the update. The workflow needs permission to create pull requests
in the repository's Actions settings. GitHub disables schedules in public
repositories after 60 days without activity.

Keep the runtime version and the GNOME CI image tags in step when changing
runtimes. Verify both SDK extension branches and installed-app behavior
against the new Platform, rather than relying on SDK-only libraries.
