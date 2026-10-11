# Signet Flatpak

A Flatpak package of [Signet](https://github.com/nosini/signet-linux), which
keeps OpenPGP keys in an encrypted KeePass vault and asks before signing or
decrypting. Signet runs an agent in the background that GnuPG and Git on your
desktop use like a regular gpg-agent, while the secret keys stay in the
vault. [Signet for Android](https://github.com/nosini/signet-android) can sync
the same vault over WebDAV.

This repository only contains the packaging. The app itself, its
documentation and its issue tracker live
[upstream](https://github.com/nosini/signet-linux).

## Installing

Install [Flatpak](https://flatpak.org/setup/) if you don't already have it,
then:

```sh
flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
flatpak install --user https://nosini.github.io/signet-flatpak/signet.flatpakref
```

This adds a remote named `signet`. Updates come through it like any other
Flatpak, from your software center or with:

```sh
flatpak update --user eu.nosini.Signet
```

The `signet` remote keeps the five previous versions. To go back to one,
find its commit with `flatpak remote-info --user --log signet
eu.nosini.Signet`, then run
`flatpak update --user --commit=COMMIT eu.nosini.Signet`. The next normal
update returns to the newest version.

The package is built for x86_64 and 64-bit Arm (aarch64).

## Using it

Start Signet from your application menu, or with:

```sh
flatpak run eu.nosini.Signet
```

Create a new vault, open an existing vault file, or download one using the
full HTTPS URL of a WebDAV file. Then choose **Import Key** to add an
OpenPGP key file. Signet asks for its passphrase when needed and prepares a
dedicated GnuPG home for it.

Use **Copy GNUPGHOME** and paste the assignment into the shell where you run
GnuPG or Git. Signet then asks for approval each time a program signs or
decrypts with your key. **Copy Git Commands** in a key's details gives the
commands that set Git up to sign commits with it. **Export Secret Key…**
saves a passphrase-protected backup of the key; other programs, such as
Seahorse, can't export it through the agent. **Manage Subkeys…** adds,
expires, revokes and deletes subkeys, and can attach an old key's subkey to
a new key so mail encrypted to it can still be decrypted.

### Using it without GNUPGHOME

To have GnuPG, Git and mail apps find Signet without setting anything, let
Signet serve GnuPG's standard home, `~/.gnupg`. It needs one extra
permission, which you grant on the host:

```sh
flatpak override --user --filesystem=~/.gnupg eu.nosini.Signet
```

Then turn on **Serve the standard GnuPG home** in Preferences, follow the
instructions it shows, reopen Signet and choose **Set Up GnuPG**. Signet
stops GnuPG's own agent when it starts, so keys stored in GnuPG itself can't
be used while Signet runs. A Flatpak mail app such as Evolution also needs
the GnuPG socket folder. Without it, the app's GnuPG starts its own agent,
which has none of your keys, and can lock the key database for everyone
else. Grant it, then restart the app:

```sh
flatpak override --user --filesystem=xdg-run/gnupg org.gnome.Evolution
flatpak kill org.gnome.Evolution
```

Closing the window keeps the agent running so GnuPG can still reach it. Use
**Quit Signet** to stop it, and **Start at login** in Preferences to start it
in the background when you log in. The
[upstream guide](https://github.com/nosini/signet-linux#installation-and-use)
describes locking, syncing and the other settings.

### Differences from a regular install

- Settings and vaults are kept separately from a native install, under
  `~/.var/app/eu.nosini.Signet/`. Vaults and key files you open are copied
  there, and the originals are left unchanged.
- Only one Signet agent can run at a time. If you used the native
  command-line service before, stop it first:

  ```sh
  systemctl --user disable --now signet.service
  ```

- Signet can't see which program on your desktop is asking to sign or
  decrypt, because those programs run outside the sandbox. Its approval
  dialog says the requester can't be identified, and it asks every time,
  even if you set it to remember approvals. If that gets in the way, for
  example when a mail app decrypts each message you open, turn off **Ask
  before decrypting** or **Ask before signing** in Preferences. Any program
  you run can then use the key for that while the vault is unlocked. A
  native install of Signet can identify Flatpak apps and remember approvals
  for each app.
- The `signet` command-line tool is included. Run it with
  `flatpak run --command=signet eu.nosini.Signet`, for example
  `flatpak run --command=signet eu.nosini.Signet status`.

## Permissions

- A window on your desktop, through Wayland or, where Wayland isn't
  available, X11, with graphics acceleration.
- Network access, to download a vault from WebDAV and keep it in sync. Signet
  has no analytics and doesn't contact keyservers.
- The desktop keyring (Secret Service), to store your WebDAV password.
- The GnuPG and Signet folders in your session's runtime directory
  (`/run/user/UID/gnupg` and `/run/user/UID/signet`), so GnuPG, Git and the
  `signet` command on your desktop can reach the agent.

It has no access to your home folder or other files, unless you grant it
`~/.gnupg` as described above. Vaults and keys you
import come through the desktop's file chooser, and starting at login goes
through the desktop's background permission.

## License

The packaging files in this repository are licensed under the GNU Affero
General Public License, version 3 (see [LICENSE](LICENSE)). Signet itself is
licensed under GPL-3.0-or-later, and its dependencies keep their own
licenses; their notices are installed with the app.

Building it yourself, publishing, and how the package works are described
in [docs/development.md](docs/development.md).
