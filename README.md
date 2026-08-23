# Chinook

**Chinook** turns a fresh Linux install into your daily driver — reproducible, opinionated, and private by design.

One command provisions packages, desktop defaults, codecs, and optional tooling:

```bash
wget -qO- https://github.com/ricardo-alternova/chinook/releases/latest/download/install | bash
```

Your username, SSH hosts, sync paths, and device IDs stay in a git-ignored `local.yml`, so the public repo never carries personal data.

| System | Desktop | Playbook | Profile Vars |
| --- | --- | --- | --- |
| Ubuntu | GNOME | `ansible/playbooks/ubuntu.yml` | `ansible/group_vars/ubuntu.yml` |
| Ubuntu Server | none (headless) | `ansible/playbooks/ubuntu_server.yml` | `ansible/group_vars/ubuntu_server.yml` |
| Fedora Asahi Remix | KDE Plasma | `ansible/playbooks/fedora_asahi.yml` | `ansible/group_vars/fedora_asahi.yml` |

Public defaults live in the profile files; your private choices live in `ansible/group_vars/local.yml`.

## Contents

- [What Chinook gives you](#what-chinook-gives-you)
- [Quick Start](#quick-start)
- [After Provisioning: Manual Steps](#after-provisioning-manual-steps)
- [What Chinook Changes](#what-chinook-changes)
- [Local Configuration](#local-configuration)
- [Feature Toggles](#feature-toggles)
- [Ubuntu (GNOME) Profile](#ubuntu-gnome-profile)
- [Ubuntu Server Profile](#ubuntu-server-profile)
- [Fedora Asahi (KDE) Profile](#fedora-asahi-kde-profile)
- [Optional Roles](#optional-roles)
- [Project Layout](#project-layout)
- [Tags](#tags)
- [Troubleshooting](#troubleshooting)
- [Notes](#notes)
- [License](#license)

## What Chinook gives you

- **Reproducible setups** — the same `local.yml` converges any machine of the same profile
- **Opinionated defaults** — dark themes, codecs, keybindings; every one can be toggled
- **Apps and codecs** — packages, snaps, and flatpaks configured for you
- **Built-in safety** — Timeshift snapshots, so recovery is automatic
- **Private by design** — nothing personal is ever committed to the repo, and `local.yml` is kept mode `0600`

## Quick Start

On a fresh Ubuntu GNOME, Ubuntu Server, or Fedora Asahi Remix KDE machine:

```bash
wget -qO- https://github.com/ricardo-alternova/chinook/releases/latest/download/install | bash
```

That one command installs `git`, `ansible`, and `python3`, clones this repo to `~/chinook`, detects your OS, and opens the app selector. After you choose what to install, it runs the matching playbook. Re-run the same command (or `~/chinook/install`) any time — the playbook is **idempotent**.

If `wget` is missing:

```bash
curl -fsSL https://github.com/ricardo-alternova/chinook/releases/latest/download/install | bash
```

The installer asks for `sudo` when it needs it. Override the checkout path with `CHINOOK_DIR`, pin a branch/tag with `CHINOOK_REF`, or force a profile with `CHINOOK_PROFILE=ubuntu|ubuntu_server|fedora_asahi`.

### Manual install

If you would rather walk the steps yourself:

1. Install prerequisites (`git`, `ansible`, `python3`):

   Ubuntu:

   ```bash
   sudo apt update
   sudo apt install git ansible python3
   ```

   Fedora:

   ```bash
   sudo dnf install git ansible python3
   ```

2. Clone and configure:

   ```bash
   git clone https://github.com/ricardo-alternova/chinook.git
   cd chinook
   python3 tools/configure.py
   ```

   Pick your profile, then toggle apps and modules. The configurator writes `ansible/group_vars/local.yml` (git-ignored).

3. Provision:

   Ubuntu GNOME:

   ```bash
   ansible-playbook ansible/playbooks/ubuntu.yml --ask-become-pass
   ```

   Ubuntu Server:

   ```bash
   ansible-playbook ansible/playbooks/ubuntu_server.yml --ask-become-pass
   ```

   Fedora Asahi:

   ```bash
   ansible-playbook ansible/playbooks/fedora_asahi.yml --ask-become-pass
   ```

   Drop `--ask-become-pass` if your user has passwordless sudo. The GNOME playbook refuses to run on a machine without `gnome-shell` and points you at `ubuntu_server.yml`. The legacy Ubuntu entrypoint `ansible/playbooks/workstation.yml` still imports `ubuntu.yml`.

4. Finish the [After Provisioning](#after-provisioning-manual-steps) checklist.

## After Provisioning: Manual Steps

Chinook installs and configures what it can, but the following need either you or a fresh session. Do them in order on a new machine.

1. **Log out and back in (or reboot).** Theme changes, app menu entries, keybindings, and udev rules apply to new sessions. On a very fresh install a reboot is the cleanest finish.

2. **Make Zsh your default shell.** Chinook installs zsh, Starship, and plugins but does **not** change your login shell:

   ```bash
   chsh -s "$(which zsh)"
   ```

   Re-login, then confirm with `echo $SHELL` → `/usr/bin/zsh`.

3. **Generate and register SSH keys.** Chinook never manages private keys — it only writes `~/.ssh/config.d/` snippets that reference keys you already have:

   ```bash
   ssh-keygen -t ed25519 -C "$USER@$(hostname)"
   cat ~/.ssh/id_ed25519.pub
   ```

   Paste the public key into GitHub, GitLab, or whichever hosts your `ssh_hosts` entries point at.

4. **Authenticate cloud and agent services.** These logins need your account and can't be automated:
   - **OneDrive** — when no `refresh_token` exists, the playbook prints the manual OAuth step. Follow it, then `onedrive --synchronize`.
   - **Agent CLIs** — run your provider's login: `opencode auth login`, `claude auth login`, `codex login`, and so on. T3 Code only drives agents whose CLIs are installed **and authenticated**.
   - **Snap/Flatpak apps** (Discord, Spotify, OnlyOffice, LocalSend, ZapZap) — sign in on first launch.

5. **Take an initial Timeshift snapshot** instead of waiting for the daily timer:

   ```bash
   sudo timeshift --create --comments "initial" --tags D
   ```

6. **On Ubuntu Server, finish remote access.** Confirm `sudo ufw status` is active with OpenSSH allowed, then join Tailscale if you enabled it (`sudo tailscale up`) and `gh auth login` if you installed the GitHub CLI. SSH back in and confirm tmux resumes the same session after disconnect.

7. **Verify your setup**:
   - `echo $SHELL` returns `/usr/bin/zsh` and the Starship prompt loads (in `kitty` on desktop, or in tmux over SSH on Server)
   - Desktop: `ffmpeg -version`, `zed`, and `flameshot` all work; Flameshot fires on `Print` (GNOME) or `Meta+Shift+4` (KDE); `t3-code` and the other apps appear in the app menu
   - Server: `tmux -V`, `btop --version`, and `gh --version` work; `sudo ufw status verbose` shows active with OpenSSH; `sudo fail2ban-client status sshd` shows the SSH jail; `tailscale status` shows the tailnet after you join

From here, treat the playbook as your update path: edit `local.yml`, re-run the profile, and Chinook converges your machine to the new state.

## What Chinook Changes

Depending on the selected profile and local config, Chinook can:

- Install apps via APT, DNF, Snap, and Flatpak
- Add or remove package repositories (Chrome, RPM Fusion)
- Remove Fedora default apps
- Configure user dotfiles and app settings
- Apply GNOME or KDE theme settings and screenshot shortcuts
- Write SSH client snippets, OneDrive config, and udev rules
- Set up Timeshift daily snapshots
- Install desktop launchers and shortcuts
- On Ubuntu Server: install Tailscale, OpenSSH server, tmux with SSH session resume, UFW, and fail2ban

## Local Configuration

`tools/configure.py` writes `ansible/group_vars/local.yml` — the git-ignored file that holds your personal values: username, home directory, SSH hosts, sync choices, device IDs, and app selections.

**Add personal packages** without touching the public profile, using the `*_extra` lists:

```yaml
apt_packages_extra:
  - example-ubuntu-package
snap_packages_extra:
  - example-snap
dnf_packages_extra:
  - example-fedora-package
flatpak_packages_extra:
  - org.example.App
```

**Keep a Fedora default app** from being removed by listing it in `dnf_remove_packages_keep`:

```yaml
dnf_remove_packages_keep:
  - plasma-welcome
```

You can also create `local.yml` manually from `ansible/group_vars/local.yml.example`. Load order is `all.yml` → `<profile>.yml` → `local.yml`; later files override earlier ones.

## Feature Toggles

Profiles provide opinionated defaults, and `local.yml` can override any toggle:

```yaml
install_packages: true
install_snap_apps: true
install_flatpak_apps: false
install_onedrive: false
install_mangohud: false
install_opencode_cli: false
install_opencode_desktop: false
install_zed: true
install_balena_etcher: false
install_t3_code: false
install_tailscale: false

configure_timeshift: true
configure_ssh: false
configure_gnome: true
configure_kde: false
configure_tmux: false
configure_ufw: false
configure_fail2ban: false
configure_keychron: false
configure_teams_pwa: false
configure_desktop_shortcuts: false
```

The configurator writes these values for you.

## Ubuntu (GNOME) Profile

**APT packages, by category:**

| Category | Packages |
| --- | --- |
| Core tools | `ansible` `git` `jq` |
| Shell & terminal | `zsh` `zsh-autosuggestions` `zsh-syntax-highlighting` `starship` `kitty` |
| Media & codecs | `ffmpeg` `gstreamer1.0-libav` `gstreamer1.0-plugins-bad` `gstreamer1.0-plugins-good` `gstreamer1.0-plugins-ugly` `gstreamer1.0-vaapi` |
| HEIC/HEIF | `heif-gdk-pixbuf` `heif-thumbnailer` `libheif-examples` `libheif-plugins-all` |
| Desktop apps | `flameshot` `gimp` `xournalpp` `google-chrome-stable` `onedrive` |
| Gaming | `steam-installer` `mangohud` |

**Snap apps:** `discord` `onlyoffice-desktopeditors` `spotify` `localsend` `zapzap`

**Also configures:**

- Google Chrome APT repository and signing key, plus `i386` foreign architecture for Steam
- Timeshift daily snapshots with 7-day retention
- GNOME dark mode and GTK theme
- Flameshot on the `Print` key
- FFmpeg/GStreamer codecs and HEIC/HEIF image support
- MangoHud overlay and Zed with `~/.local/bin` on the Zsh path

Optional modules: OneDrive, SSH snippets, Keychron udev rules, OBS Studio, OpenCode CLI/Desktop, Balena Etcher, Teams PWA, desktop shortcuts, T3 Code, tmux, and Tailscale. Enable them in `local.yml` or through `tools/configure.py`.

## Ubuntu Server Profile

This profile is for a headless Ubuntu box you SSH into — a remote agent machine, not a daily-driver desktop. It skips GNOME, snaps, browsers, and every other GUI role.

**APT packages, by category:**

| Category | Packages |
| --- | --- |
| Core tools | `ansible` `curl` `git` `jq` `openssh-server` |
| Shell & terminal | `zsh` `zsh-autosuggestions` `zsh-syntax-highlighting` `starship` `tmux` |
| Ops | `btop` `gh` |
| Security | `ufw` `fail2ban` (installed by their roles) |

**Also configures:**

- Timeshift daily snapshots with 7-day retention (CLI + systemd timer)
- tmux with mouse support and a colorable status bar
- Automatic tmux attach on interactive SSH (`SSH_TTY`) for bash and zsh, so disconnecting and reconnecting resumes the same session. An existing `~/.tmux.conf` is left alone.
- Tailscale client install (`tailscaled` enabled). Prefer `sudo tailscale up` interactively. An optional `tailscale_auth_key` is passed via `TS_AUTHKEY` (not the process argv). Use a single-use key if you store one in `local.yml`
- UFW with default-deny inbound, allow outbound, OpenSSH allowed before the firewall is turned on, and `tailscale0` allowed when Tailscale is enabled so tailnet traffic is not blocked
- fail2ban SSH jail (`jail.d/sshd.local` only — package `jail.conf` is left alone) using the systemd journal, 5 retries / 10 minutes / 1 hour ban. Localhost is ignored; Tailscale/CGNAT addresses are not, so a compromised tailnet peer can still be banned

Optional modules: SSH snippets, OneDrive, OpenCode CLI, Codex CLI, T3 Code, and Keychron udev rules. Desktop apps (Kitty, Chrome, Steam, Zed, snaps, GNOME settings) are not offered in the Server configurator.

Open extra ports in `local.yml` without replacing the SSH rule:

```yaml
ufw_allowed_ports:
  - 80/tcp
  - 443/tcp
```

### Remote agent workflow

The Server profile is meant to be a box you leave running and connect to from a laptop:

1. **SSH + tmux.** Interactive SSH drops you into a named tmux session. Work survives laptop sleep, network changes, and closing the lid. Give each machine a different `tmux_status_bg` (for example `green`, `red`, `colour24`) so you can tell them apart.
2. **Tailscale.** Reach the box from outside the LAN without exposing extra ports to the public internet. After `sudo tailscale up`, use the MagicDNS name from any device on the tailnet. Optional: set `tailscale_ssh: true` (with an auth key) if you want Tailscale SSH. UFW still allows OpenSSH so a local or tailnet SSH session is not locked out.
3. **UFW + fail2ban.** Inbound traffic is denied except SSH (and Tailscale). fail2ban bans IPs that hammer SSH. This is the baseline before you put the box on a network.
4. **Agent CLIs on the box, not the laptop.** Enable OpenCode CLI, Codex CLI, and/or T3 Code in `local.yml`. Long-running agent jobs then keep going after you disconnect. Authenticate on the server (`gh auth login`, `codex login`, `opencode auth login`).
5. **T3 Code for screenshots and a GUI.** Pasting images over raw SSH is unreliable. Install T3 Code on the server and connect to it from the T3 desktop/mobile app over Tailscale. The AppImage role is headless-safe: missing `update-desktop-database` / `gtk-update-icon-cache` is ignored.
6. **Passwordless SSH between machines.** Chinook never writes private keys. Generate them, register the public key, and add `ssh_hosts` entries so your laptop (or an agent on it) can hop to the server without a password.

Hardware KVMs and out-of-band power buttons are useful for this kind of box, but they are out of scope for the playbook.

## Fedora Asahi (KDE) Profile

**DNF packages, by category:**

| Category | Packages |
| --- | --- |
| Core tools | `ansible` `git` `jq` `curl` |
| Shell & terminal | `zsh` `zsh-autosuggestions` `zsh-syntax-highlighting` `starship` `kitty` |
| Browser | `chromium` |
| Media & codecs | `ffmpeg` `ffmpegthumbnailer` `gstreamer1-libav` `gstreamer1-plugin-openh264` `gstreamer1-plugins-bad-free` `gstreamer1-plugins-bad-free-extras` `gstreamer1-plugins-bad-freeworld` `gstreamer1-plugins-good` `gstreamer1-plugins-good-extras` `gstreamer1-plugins-ugly` `lame` `lame-libs` `libavcodec-freeworld` `mozilla-openh264` `openh264` `pipewire-codec-aptx` |
| Desktop apps | `flameshot` |

**Flatpak apps:** `org.onlyoffice.desktopeditors` `org.localsend.localsend_app`

**Also configures:**

- RPM Fusion free and nonfree repositories for codecs
- Timeshift daily snapshots with 7-day retention
- KDE Breeze Dark theme
- Flameshot on `Meta+Shift+4`
- Zed with `~/.local/bin` on the Zsh path
- Removal of the default Fedora games, maps, weather, and welcome apps when present

Google Chrome is not installed here because official Linux builds don't exist for Apple Silicon — Chromium is used instead. The terminal UI includes a step to keep any removed default apps if you want them.

## Optional Roles

### T3 Code

T3 Code is an agent-harness control surface that drives Claude Code, Codex, Cursor, Grok Build, and OpenCode. The `t3_code` role downloads the desktop AppImage into `/opt/t3-code` and adds a `t3-code` launcher and desktop entry.

The only published Linux build is **x86_64**; on Fedora Asahi (aarch64) the AppImage runs through the x86 emulation layer, so the same install works on both distros. T3 Code needs at least one provider CLI installed and authenticated to drive agents — such as the optional OpenCode CLI.

### Codex CLI

The `codex_cli` role installs the official Codex CLI via the installer script (`curl -fsSL https://chatgpt.com/codex/install.sh | sh`), landing the `codex` binary in `~/.local/bin`. It's idempotent: the installer only re-downloads when a newer release is available, and the role runs it non-interactively.

### Zed Defaults

The Zed role only creates `settings.json` when one doesn't already exist. The template enables dark theme, disables telemetry, trusts worktrees, and configures `codex-acp` and `claude-acp` agent servers with permissive modes. Review `ansible/roles/zed/templates/settings.json.j2` before using these defaults on a machine where they're not desired.

## Project Layout

| Path | Purpose |
| --- | --- |
| `install` | One-line bootstrap: prereqs, clone, OS detect, configure, playbook |
| `ansible/playbooks/ubuntu.yml` | Ubuntu GNOME playbook |
| `ansible/playbooks/ubuntu_server.yml` | Ubuntu Server playbook |
| `ansible/playbooks/fedora_asahi.yml` | Fedora Asahi KDE playbook |
| `ansible/playbooks/workstation.yml` | Backward-compatible Ubuntu GNOME wrapper |
| `ansible/playbooks/tasks/load_local_vars.yml` | Shared `local.yml` loader used by every playbook |
| `ansible/group_vars/all.yml` | Shared generic defaults |
| `ansible/group_vars/ubuntu.yml` | Ubuntu GNOME profile |
| `ansible/group_vars/ubuntu_server.yml` | Ubuntu Server profile |
| `ansible/group_vars/fedora_asahi.yml` | Fedora Asahi KDE profile |
| `ansible/group_vars/local.yml.example` | Template for the private override file |
| `ansible/roles/` | One role per workstation concern |
| `tools/configure.py` | Terminal UI that generates `local.yml` |

## Tags

Run one role at a time:

```bash
ansible-playbook ansible/playbooks/fedora_asahi.yml --tags packages
```

Available tags match role names:

```bash
packages snaps flatpaks timeshift tmux tailscale ufw fail2ban ssh_client
onedrive gnome kde mangohud opencode_cli opencode_desktop codex_cli t3_code
keychron zed balena_etcher teams_pwa desktop_shortcuts
```

## Troubleshooting

- **`sudo a password is required` throughout the run** — your account needs passwordless sudo, or you must keep `--ask-become-pass`. To enable it, run `sudo visudo` and add `your-user ALL=(ALL) NOPASSWD: ALL`.
- **The one-line installer says it needs an interactive terminal** — run it from a real terminal (desktop or SSH). `wget | bash` still works because prompts are read from `/dev/tty`.
- **`This playbook is for Ubuntu GNOME`** — you ran `ubuntu.yml` on a machine without `gnome-shell`. Use `ansible/playbooks/ubuntu_server.yml` instead.
- **GNOME/KDE tasks fail with "no display" or DBus errors** — the theme and shortcut roles configure a running desktop session via `gsettings`/`kwriteconfig`. Run the GNOME or KDE playbook from a logged-in GUI session, not a bare TTY or a server SSH login.
- **SSH drops you into tmux and you wanted a plain shell** — set `configure_tmux: false` in `local.yml` and re-run, or detach with the usual tmux prefix. Auto-attach only runs on interactive SSH (`SSH_TTY`) from `.bashrc` and `.zshrc`, so `scp`, `sftp`, and Ansible are unaffected. An existing `~/.tmux.conf` is never overwritten.
- **tmux did not start and you still have a shell** — Chinook no longer `exec`s tmux. If tmux fails, the login shell stays up. If tmux starts and you detach, the SSH session exits.
- **Tailscale is installed but not connected** — run `sudo tailscale up`. Storing `tailscale_auth_key` in `local.yml` is optional; use a single-use key. The playbook and configurator keep `local.yml` mode `0600`.
- **fail2ban banned your Tailscale IP** — the default ignore list is localhost only. Add your admin tailnet address to `fail2ban_ignoreip` rather than the whole `100.64.0.0/10` range.
- **Locked out after enabling UFW** — use console or a local session and run `sudo ufw allow OpenSSH` or `sudo ufw disable`. The Server profile allows OpenSSH before enabling UFW; this usually means SSH is on a non-standard port — add it to `ufw_allowed_ports`.
- **fail2ban is not banning** — confirm `sudo fail2ban-client status sshd` and that `python3-systemd` is installed so the jail can read the journal.
- **T3 Code won't start on Fedora Asahi** — the x86_64 AppImage may not mount FUSE through the emulation layer even with `fuse-libs` installed. Fall back to extraction, which needs no FUSE:

  ```bash
  /opt/t3-code/T3-Code.AppImage --appimage-extract-and-run
  ```

- **New apps or icons don't appear in the app menu** — re-login, or refresh the icon cache:

  ```bash
  sudo gtk-update-icon-cache -f /usr/share/icons/hicolor
  ```

- **AppImage errors about `libfuse.so.2`** — the FUSE 2 library is installed automatically by the role (`libfuse2t64` on Ubuntu, `fuse-libs` on Fedora); install it manually if it's still missing.
- **Want a module not in the terminal UI** — add the role to the profile's playbook gated by a toggle from `all.yml`, or keep it simple with the `*_extra` package lists.

## Notes

- OneDrive OAuth is not automated; if no refresh token exists the playbook prints the manual authentication step.
- Private SSH keys are never managed by this repository; SSH snippets reference keys that already exist on the machine.

## License

Chinook is released under the [MIT License](LICENSE).
