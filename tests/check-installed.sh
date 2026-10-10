# shellcheck shell=sh
# Runs inside the installed app's sandbox (see scripts/test-installed.sh).
# There is no display, sound server or session bus in CI, so keep these checks
# headless: start the command-line interface, import modules, look for files.
set -eu

test -x /app/bin/signet-launch
test -x /app/bin/signet-gui
test -x /app/bin/signet
signet --version
signet --help > /dev/null
signet-gui --help > /dev/null
gpg --version
gpgconf --version
curl --version

test -f /app/share/applications/eu.nosini.Signet.desktop
test -f /app/share/metainfo/eu.nosini.Signet.metainfo.xml
test -f /app/share/icons/hicolor/scalable/apps/eu.nosini.Signet.svg

# The agent must use the runtime path host GnuPG also computes, rather than
# falling back to a socket in the sandbox's home directory.
test -d "$XDG_RUNTIME_DIR/gnupg"
test -d "$XDG_RUNTIME_DIR/signet"
home=$(mktemp -d)
trap 'rm -rf "$home"' EXIT
socket=$(gpgconf --homedir "$home" --list-dirs agent-socket)
case "$socket" in
  "$XDG_RUNTIME_DIR"/gnupg/*/S.gpg-agent) ;;
  *) echo "Unexpected GnuPG socket path: $socket" >&2; exit 1 ;;
esac

# flatpak-builder records the license files it finds at the root of each
# module's source; the main module's must be there.
test -n "$(ls "/app/share/licenses/$FLATPAK_ID/signet")"

echo 'Installed app checks passed.'
