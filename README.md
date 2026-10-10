# Signet Flatpak

Signet keeps OpenPGP keys in an encrypted KeePass vault and asks before
signing or decrypting. This package runs the Linux app in a Flatpak sandbox
and connects its agent to GnuPG and Git on your desktop.

## Installation and use

Build and install the package using the [development guide](docs/development.md#building).
Then launch **Signet** from your application menu, or run:

```sh
flatpak run eu.nosini.Signet
```

Create a vault, select an existing vault file, or download one from WebDAV.
Vaults and optional key files selected through the file chooser are copied
into the app's private storage. Import an OpenPGP key file, then use **Copy
GNUPGHOME** to get the shell assignment for host GnuPG. Paste it into the
shell where you use GnuPG or Git. A key's details include Git signing commands.
Secret keys stay in the vault; the dedicated GnuPG home holds public certificates.

Closing the window keeps the agent running. Use **Quit Signet** to stop it.
Preferences offers **Start at login**, using the desktop's Background portal.
If a native Signet service is running, stop it before starting this app:

```sh
systemctl --user disable --now signet.service
```

The Flatpak uses separate settings and storage under
`~/.var/app/eu.nosini.Signet/`. It does not open a native installation's vault
automatically. Choose the vault through the file picker or sync it over
WebDAV. Run CLI commands for this installation with
`flatpak run --command=signet eu.nosini.Signet status`.

Host requests arrive from outside the app's process namespace. Signet may
show them as unidentified callers and always asks for approval for those
requests, even if approval reuse is enabled.

## Permissions and privacy

The app can use Wayland or X11 and graphics acceleration to display its
window and prompts. Network access downloads and syncs encrypted vaults
over WebDAV. The desktop Secret Service stores WebDAV passwords.

The GnuPG and Signet runtime directories are shared so host GnuPG, Git and
command-line clients can reach the agent. File access is granted through
the desktop file chooser; the package has no blanket home-directory access.
Login startup is requested through a portal.

Signet has no analytics or keyserver traffic. Protect your vault password,
key file and backups. See the [upstream documentation](https://github.com/nosini/signet-linux)
for vault storage and synchronization details.

## License

Packaging files are licensed under AGPL-3.0; see [LICENSE](LICENSE).
Signet is GPL-3.0-or-later. Its third-party notices are included in the
upstream source.
