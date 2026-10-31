#!/usr/bin/env python3
from pathlib import Path
import argparse
import glob
import os
import re
import shutil
import socket
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
LOCAL_VARS = ROOT / "ansible" / "group_vars" / "local.yml"
TMUX_SESSION_NAME_RE = re.compile(r"[A-Za-z0-9_-]+")
HOSTNAME_RE = re.compile(r"[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?")


LINUX_PROFILES = ("ubuntu", "ubuntu_server", "fedora_asahi")
ALL_PROFILES = LINUX_PROFILES + ("macos",)
DESKTOP_PROFILES = ("ubuntu", "fedora_asahi")
DESKTOPS_AND_MACOS = DESKTOP_PROFILES + ("macos",)
APT_PROFILES = ("ubuntu", "ubuntu_server")
PLAYBOOKS = {
    "ubuntu": "ansible/playbooks/ubuntu.yml",
    "ubuntu_server": "ansible/playbooks/ubuntu_server.yml",
    "fedora_asahi": "ansible/playbooks/fedora_asahi.yml",
    "macos": "ansible/playbooks/macos.yml",
}
# Apps without "profiles" are Linux only. On macOS, "brew" lists Homebrew
# formulae and "cask" Homebrew casks; only apps with "macos_default" start ticked.

APPS = [
    {
        "key": "base_cli",
        "label": "Base CLI tools",
        "default": True,
        "profiles": ALL_PROFILES,
        "apt": ["ansible", "curl", "git", "jq"],
        "dnf": ["ansible", "git", "jq", "curl"],
        "brew": ["git", "jq"],
    },
    {
        "key": "timeshift",
        "label": "Timeshift daily snapshots (system restore points)",
        "default": True,
        "profiles": LINUX_PROFILES,
        "flag": "configure_timeshift",
        # A module, not an app: don't re-tick it just because the package exists.
        "no_detect": True,
    },
    {
        "key": "shell",
        "label": "Zsh, Starship, and zsh plugins",
        "default": True,
        "apt": ["zsh", "zsh-autosuggestions", "zsh-syntax-highlighting"],
        "dnf": ["zsh", "zsh-autosuggestions", "zsh-syntax-highlighting"],
        "flags": ["install_starship", "configure_shell"],
    },
    {
        "key": "tmux",
        "label": "tmux with SSH session resume",
        "default_profiles": ["ubuntu_server"],
        "apt": ["tmux"],
        "dnf": ["tmux"],
        "flag": "configure_tmux",
    },
    {
        "key": "btop",
        "label": "btop process viewer",
        "default_profiles": ["ubuntu_server"],
        "profiles": ALL_PROFILES,
        "apt": ["btop"],
        "dnf": ["btop"],
        "brew": ["btop"],
    },
    {
        "key": "gh",
        "label": "GitHub CLI",
        "default_profiles": ["ubuntu_server"],
        "profiles": ALL_PROFILES,
        "apt": ["gh"],
        "dnf": ["gh"],
        "brew": ["gh"],
    },
    {
        "key": "tailscale",
        "label": "Tailscale (install only; join is manual)",
        "detect_paths": ["/usr/bin/tailscale"],
        "default_profiles": ["ubuntu_server"],
        "flag": "install_tailscale",
    },
    {
        "key": "ufw",
        "label": "UFW firewall (deny inbound, allow SSH)",
        "detect": "ufw_enabled",
        "profiles": APT_PROFILES,
        "default_profiles": ["ubuntu_server"],
        "flag": "configure_ufw",
    },
    {
        "key": "fail2ban",
        "label": "fail2ban (ban repeated SSH failures)",
        "detect_packages": ["fail2ban"],
        "default_profiles": ["ubuntu_server"],
        "flag": "configure_fail2ban",
    },
    {"key": "kitty", "label": "Kitty terminal (Catppuccin Mocha)", "default": True, "profiles": DESKTOP_PROFILES, "apt": ["kitty"], "dnf": ["kitty"], "flag": "configure_kitty"},
    {
        "key": "codecs",
        "label": "Audio/video codecs",
        "default": True,
        "profiles": DESKTOP_PROFILES,
        "apt": [
            "ffmpeg",
            "gstreamer1.0-libav",
            "gstreamer1.0-plugins-bad",
            "gstreamer1.0-plugins-good",
            "gstreamer1.0-plugins-ugly",
            "gstreamer1.0-vaapi",
        ],
        "dnf": [
            "ffmpeg",
            "ffmpegthumbnailer",
            "gstreamer1-libav",
            "gstreamer1-plugin-openh264",
            "gstreamer1-plugins-bad-free-extras",
            "gstreamer1-plugins-bad-free",
            "gstreamer1-plugins-bad-freeworld",
            "gstreamer1-plugins-good",
            "gstreamer1-plugins-good-extras",
            "gstreamer1-plugins-ugly",
            "lame",
            "lame-libs",
            "libavcodec-freeworld",
            "mozilla-openh264",
            "openh264",
            "pipewire-codec-aptx",
        ],
        "rpmfusion": True,
    },
    {
        "key": "heif",
        "label": "HEIC/HEIF image support",
        "default": True,
        "profiles": DESKTOP_PROFILES,
        "apt": ["heif-gdk-pixbuf", "heif-thumbnailer", "libheif-examples", "libheif-plugin-libde265", "libheif-plugin-aomdec"],
    },
    {"key": "chrome", "label": "Google Chrome on Ubuntu / Chromium on Fedora Asahi", "macos_label": "Google Chrome", "default": True, "profiles": DESKTOPS_AND_MACOS, "apt": ["google-chrome-stable"], "dnf": ["chromium"], "cask": ["google-chrome"], "detect_paths": ["/Applications/Google Chrome.app"]},
    {"key": "wayshot", "label": "WayShot (screenshot annotate)", "default": True, "profiles": DESKTOP_PROFILES, "flatpak": ["io.github.gutopardini.wayshot"]},
    {"key": "input_remapper", "label": "input-remapper (remap mouse buttons and wheel)", "default": False, "profiles": DESKTOP_PROFILES, "apt": ["input-remapper"], "dnf": ["input-remapper"]},
    {"key": "helium", "label": "Helium browser (privacy-first Chromium fork)", "default": False, "profiles": DESKTOP_PROFILES, "flag": "install_helium", "detect_packages": ["helium-bin"]},
    {"key": "unity_hub", "label": "Unity Hub (Unity game engine)", "default": False, "profiles": ["ubuntu"], "flag": "install_unity_hub", "detect_packages": ["unityhub"]},
    {"key": "gimp", "label": "GIMP", "default": False, "profiles": DESKTOPS_AND_MACOS, "apt": ["gimp"], "dnf": ["gimp"], "cask": ["gimp"], "detect_paths": ["/Applications/GIMP.app"]},
    {"key": "xournalpp", "label": "Xournal++", "default": False, "profiles": DESKTOP_PROFILES, "apt": ["xournalpp"], "dnf": ["xournalpp"]},
    {"key": "onedrive", "label": "OneDrive", "default": False, "apt": ["onedrive"], "dnf": ["onedrive"], "flag": "install_onedrive"},
    {"key": "mangohud", "label": "MangoHud", "default": False, "profiles": DESKTOP_PROFILES, "apt": ["mangohud"], "dnf": ["mangohud"], "flag": "install_mangohud"},
    {"key": "obs_studio", "label": "OBS Studio", "default": False, "profiles": DESKTOPS_AND_MACOS, "apt": ["obs-studio"], "dnf": ["obs-studio"], "cask": ["obs"], "detect_paths": ["/Applications/OBS.app"]},
    {"key": "opencode_cli", "label": "OpenCode CLI", "default": True, "profiles": ALL_PROFILES, "flag": "install_opencode_cli", "detect_paths": ["~/.opencode/bin/opencode"]},
    {"key": "codex_cli", "label": "Codex CLI", "default": False, "profiles": ALL_PROFILES, "flag": "install_codex_cli", "detect_paths": ["~/.local/bin/codex"]},
    {"key": "claude_code", "label": "Claude Code", "default": True, "profiles": ALL_PROFILES, "flag": "install_claude_code", "detect_paths": ["~/.local/bin/claude"]},
    {"key": "cursor_cli", "label": "Cursor CLI (agent)", "default": True, "profiles": ALL_PROFILES, "flag": "install_cursor_cli", "detect_paths": ["~/.local/bin/cursor-agent"]},
    {"key": "glab", "label": "GitLab CLI (glab)", "default": True, "profiles": ALL_PROFILES, "flag": "install_glab", "detect_packages": ["glab"], "brew": ["glab"]},
    {"key": "docker", "label": "Docker Engine (with Compose and Buildx)", "default": True, "flag": "install_docker", "detect_packages": ["docker-ce"]},
    {"key": "fleet", "label": "Fleet (fleetd device management, needs the enroll secret)", "default": False, "macos_default": True, "profiles": ALL_PROFILES, "flag": "install_fleet", "detect_packages": ["fleet-osquery"], "detect_paths": ["/Library/LaunchDaemons/com.fleetdm.orbit.plist"]},
    {"key": "compai_agent", "label": "Comp AI device agent (compliance checks)", "default": False, "profiles": LINUX_PROFILES, "flag": "install_compai_agent", "detect_packages": ["comp-ai-device-agent"]},
    {"key": "unity_cli", "label": "Unity CLI (beta)", "default": False, "flag": "install_unity_cli", "detect_paths": ["~/.local/bin/unity"]},
    {"key": "grok_bot", "label": "Grok Bot (xAI desktop agent)", "default": False, "profiles": DESKTOP_PROFILES, "flag": "install_grok_bot", "detect_paths": ["/usr/bin/grok-bot"]},
    {"key": "cursor", "label": "Cursor editor", "default": False, "profiles": DESKTOPS_AND_MACOS, "flag": "install_cursor", "detect_paths": ["/usr/bin/cursor", "/Applications/Cursor.app"], "cask": ["cursor"]},
    {"key": "t3_code", "label": "T3 Code (remote agent control surface)", "default": False, "flag": "install_t3_code", "detect_paths": ["/usr/local/bin/t3-code"]},
    {"key": "steam", "label": "Steam", "default": False, "profiles": DESKTOP_PROFILES, "apt": ["steam-installer"], "foreign_arch": ["i386"]},
    {"key": "discord", "label": "Discord", "default": False, "profiles": DESKTOPS_AND_MACOS, "snap": ["discord"], "flatpak": ["com.discordapp.Discord"], "cask": ["discord"], "detect_paths": ["/Applications/Discord.app"]},
    {"key": "onlyoffice", "label": "OnlyOffice", "default": True, "profiles": DESKTOPS_AND_MACOS, "snap": ["onlyoffice-desktopeditors"], "flatpak": ["org.onlyoffice.desktopeditors"], "cask": ["onlyoffice"], "detect_paths": ["/Applications/ONLYOFFICE.app"]},
    {"key": "spotify", "label": "Spotify", "default": False, "profiles": DESKTOPS_AND_MACOS, "snap": ["spotify"], "flatpak": ["com.spotify.Client"], "cask": ["spotify"], "detect_paths": ["/Applications/Spotify.app"]},
    {"key": "localsend", "label": "LocalSend", "default": True, "profiles": DESKTOPS_AND_MACOS, "snap": ["localsend"], "flatpak": ["org.localsend.localsend_app"], "cask": ["localsend"], "detect_paths": ["/Applications/LocalSend.app"]},
    {"key": "zapzap", "label": "ZapZap", "default": False, "profiles": DESKTOP_PROFILES, "snap": ["zapzap"]},
    {"key": "zed", "label": "Zed editor", "default": True, "profiles": DESKTOPS_AND_MACOS, "flag": "install_zed", "detect_paths": ["~/.local/bin/zed", "/Applications/Zed.app"], "cask": ["zed"]},
    {"key": "balena_etcher", "label": "Balena Etcher", "default": False, "profiles": DESKTOP_PROFILES, "flag": "install_balena_etcher", "detect_paths": ["/opt/balena-etcher-*/balenaEtcher-linux-x64/balena-etcher"]},
    {"key": "teams_pwa", "label": "Microsoft Teams PWA", "default": False, "profiles": DESKTOP_PROFILES, "flag": "configure_teams_pwa", "detect_paths": ["/etc/opt/chrome/policies/managed/teams-pwa.json"]},
    {"key": "keychron", "label": "Keychron udev rule", "default": False, "flag": "configure_keychron", "detect_paths": ["/etc/udev/rules.d/50-keychron-k4-pro.rules"]},
]


FEDORA_REMOVALS = [
    "aisleriot",
    "bovo",
    "five-or-more",
    "four-in-a-row",
    "granatier",
    "gnome-chess",
    "gnome-klotski",
    "gnome-mahjongg",
    "gnome-maps",
    "gnome-mines",
    "gnome-nibbles",
    "gnome-robots",
    "gnome-sudoku",
    "gnome-taquin",
    "gnome-tetravex",
    "gnome-tour",
    "gnome-weather",
    "hitori",
    "iagno",
    "kajongg",
    "kapman",
    "katomic",
    "kblocks",
    "kmahjongg",
    "kmines",
    "knavalbattle",
    "knetwalk",
    "kolf",
    "kollision",
    "konquest",
    "kpat",
    "ksquares",
    "ksudoku",
    "kubrick",
    "kweather",
    "lightsoff",
    "libreoffice*",
    "lskat",
    "marble",
    "palapeli",
    "picmi",
    "plasma-welcome",
    "quadrapassel",
    "swell-foop",
    "tali",
]


def current_hostname():
    return socket.gethostname().split(".")[0].lower()


def ask(prompt, default=""):
    suffix = f" [{default}]" if default else ""
    value = input(f"{prompt}{suffix}: ").strip()
    return value or default


def ask_yes_no(prompt, default=True):
    suffix = "Y/n" if default else "y/N"
    value = input(f"{prompt} [{suffix}]: ").strip().lower()
    if not value:
        return default
    return value in {"y", "yes"}


def choose_one(title, choices):
    print(f"\n{title}")
    for index, (_, label) in enumerate(choices, start=1):
        print(f"  {index}. {label}")
    while True:
        value = input("Choose one: ").strip()
        if value.isdigit() and 1 <= int(value) <= len(choices):
            return choices[int(value) - 1][0]
        print("Enter a valid number.")


def choose_many(title, choices, default_keys):
    selected = set(default_keys)
    while True:
        print(f"\n{title}")
        for index, item in enumerate(choices, start=1):
            marker = "x" if item["key"] in selected else " "
            print(f"  {index:2}. [{marker}] {item['label']}")
        print("Enter numbers to toggle, 'a' for all, 'n' for none, or press Enter to continue.")
        value = input("> ").strip().lower()
        if not value:
            return selected
        if value == "a":
            selected = {item["key"] for item in choices}
            continue
        if value == "n":
            selected = set()
            continue
        changed = False
        for part in value.replace(",", " ").split():
            if part.isdigit() and 1 <= int(part) <= len(choices):
                key = choices[int(part) - 1]["key"]
                if key in selected:
                    selected.remove(key)
                else:
                    selected.add(key)
                changed = True
        if not changed:
            print("Enter numbers to toggle, 'a' for all, 'n' for none, or press Enter to continue.")


_YAML_BOOLISH = {
    "y",
    "n",
    "yes",
    "no",
    "true",
    "false",
    "on",
    "off",
    "null",
    "~",
}


def yaml_value(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    text = str(value)
    if text == "":
        return '""'
    needs_quotes = (
        text != text.strip()
        or text.lower() in _YAML_BOOLISH
        or text[:1] in "-?:{}[]&,*#|>!%@`'\""
        or any(char in text for char in ":#{}[]&,*?|<>=!%@`'\"\\\t\n ")
    )
    if needs_quotes:
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return text


def write_scalar(lines, key, value):
    lines.append(f"{key}: {yaml_value(value)}")


def write_list(lines, key, values):
    if not values:
        lines.append(f"{key}: []")
        return
    lines.append(f"{key}:")
    for value in values:
        lines.append(f"  - {yaml_value(value)}")


def unique(values):
    result = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


def app_flags(app):
    return app.get("flags", [app["flag"]] if "flag" in app else [])


def app_visible(app, profile):
    return profile in app.get("profiles", LINUX_PROFILES)


def app_default(app, profile):
    if profile == "macos":
        return app.get("macos_default", False)
    if "default_profiles" in app:
        return profile in app["default_profiles"]
    return app.get("default", False)


def app_label(app, profile):
    return app.get("macos_label", app["label"]) if profile == "macos" else app["label"]


def profile_managers(profile):
    """Package managers whose lists an app uses on this profile, in order of preference."""
    if profile in APT_PROFILES:
        return ["apt", "snap", "flatpak"]
    if profile == "macos":
        return ["brew", "cask"]
    return ["dnf", "flatpak"]


MANAGER_LISTS = {
    "apt": "apt_packages",
    "snap": "snap_packages",
    "flatpak": "flatpak_packages",
    "dnf": "dnf_packages",
    "brew": "brew_packages",
    "cask": "brew_casks",
}


def visible_apps(profile):
    return [app for app in APPS if app_visible(app, profile)]


def default_selection(profile):
    return {app["key"] for app in visible_apps(profile) if app_default(app, profile)}


def command_lines(argv):
    if not shutil.which(argv[0]):
        return []
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return []
    return result.stdout.splitlines() if result.returncode == 0 else []


def installed_packages():
    """Return the names installed by each package manager on this machine."""
    dpkg = {
        line.split()[1]
        for line in command_lines(["dpkg-query", "-W", "-f", "${db:Status-Abbrev} ${Package}\n"])
        if line.startswith("ii") and len(line.split()) > 1
    }
    rpm = set(command_lines(["rpm", "-qa", "--qf", "%{NAME}\n"]))
    snap = {line.split()[0] for line in command_lines(["snap", "list"])[1:] if line.split()}
    flatpak = {line.strip() for line in command_lines(["flatpak", "list", "--app", "--columns=application"]) if line.strip()}
    brew = brew_path()
    formulae = set(command_lines([brew, "list", "--formula", "-1"])) if brew else set()
    casks = set(command_lines([brew, "list", "--cask", "-1"])) if brew else set()
    return {
        "apt": dpkg,
        "dnf": rpm,
        "snap": snap,
        "flatpak": flatpak,
        "brew": formulae,
        "cask": casks,
        "system": dpkg | rpm | formulae | casks,
    }


def brew_path():
    # A fresh shell may not have Homebrew on PATH yet.
    for path in (shutil.which("brew"), "/opt/homebrew/bin/brew", "/usr/local/bin/brew"):
        if path and os.access(path, os.X_OK):
            return path
    return None


def ufw_enabled():
    try:
        text = Path("/etc/ufw/ufw.conf").read_text(encoding="utf-8")
    except OSError:
        return False
    return re.search(r"^ENABLED=yes\s*$", text, re.MULTILINE) is not None


def app_installed(app, profile, packages):
    if app.get("detect") == "ufw_enabled":
        return ufw_enabled()
    # /Applications belongs to macOS; a Linux profile never installs there.
    paths = app.get("detect_paths", [])
    if profile != "macos":
        paths = [path for path in paths if not path.startswith("/Applications/")]
    if any(glob.glob(os.path.expanduser(path)) for path in paths):
        return True
    if any(name in packages["system"] for name in app.get("detect_packages", [])):
        return True
    for manager in profile_managers(profile):
        names = app.get(manager)
        if names:
            return all(name in packages[manager] for name in names)
    return False


def detect_installation(profile):
    """Installed app keys, and casks already in /Applications outside Homebrew.

    The second set is what lets the configurator avoid calling `brew install`
    (which downloads the whole artifact before noticing the app is present) for
    apps the user installed from a website or the App Store.
    """
    if profile == "macos":
        if sys.platform != "darwin":
            return set(), set()
    elif not sys.platform.startswith("linux"):
        return set(), set()
    packages = installed_packages()
    installed = {app["key"] for app in visible_apps(profile) if app_installed(app, profile, packages)}
    unmanaged_casks = set()
    if profile == "macos":
        for app in visible_apps(profile):
            if app["key"] not in installed or not app.get("cask"):
                continue
            if all(name in packages["cask"] for name in app["cask"]):
                continue
            if any(
                glob.glob(os.path.expanduser(path))
                for path in app.get("detect_paths", [])
                if path.startswith("/Applications/")
            ):
                unmanaged_casks.add(app["key"])
    return installed, unmanaged_casks


def detect_installed(profile):
    """Keys of the apps that are already on this machine."""
    return detect_installation(profile)[0]


def read_local_yml(path):
    """Parse the scalars and lists of a local.yml written by this tool."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return None
    return read_local_yml_text(text)


def read_local_yml_text(text):
    data = {}
    current = None
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith("  - ") and current is not None:
            data[current].append(line[4:].strip().strip('"'))
            continue
        match = re.match(r"([A-Za-z0-9_]+):\s*(.*)$", line)
        if not match:
            current = None
            continue
        key, value = match.groups()
        if value == "":
            data[key] = []
            current = key
        else:
            current = None
            data[key] = {"true": True, "false": False, "[]": []}.get(value, value.strip('"'))
    return data


def previous_selection(profile, data):
    """Keys of the apps a previous local.yml selected."""
    selected = set()
    for app in visible_apps(profile):
        flags = app_flags(app)
        if flags:
            if all(data.get(flag) is True for flag in flags):
                selected.add(app["key"])
            continue
        for manager in profile_managers(profile):
            names = app.get(manager)
            if names:
                chosen = data.get(MANAGER_LISTS[manager])
                if isinstance(chosen, list) and all(name in chosen for name in names):
                    selected.add(app["key"])
                break
    return selected


def generate_local_yml(profile, config):
    # workstation_user and workstation_home are left to all.yml, which takes them
    # from the account running the playbook.
    lines = ["# Generated by tools/configure.py", f"profile: {profile}", ""]

    for key in sorted(k for k, v in config.items() if isinstance(v, bool)):
        write_scalar(lines, key, config[key])
    lines.append("")

    for key in [
        "apt_packages",
        "apt_foreign_architectures",
        "snap_packages",
        "dnf_packages",
        "dnf_remove_packages",
        "rpmfusion_release_packages",
        "flatpak_packages",
        "brew_packages",
        "brew_casks",
        "brew_casks_present",
        "onedrive_sync_list",
    ]:
        if key in config:
            write_list(lines, key, config[key])
    lines.append("")

    if "ssh_hosts" in config:
        lines.append("ssh_hosts:")
        for host in config["ssh_hosts"]:
            lines.append(f"  - host: {yaml_value(host['host'])}")
            lines.append(f"    hostname: {yaml_value(host['hostname'])}")
            lines.append(f"    user: {yaml_value(host['user'])}")
            lines.append(f"    identity_file: {yaml_value(host['identity_file'])}")

    for key in [
        "onedrive_sync_dir",
        "keychron_vendor_id",
        "keychron_product_id",
        "teams_pwa_app_id",
        "teams_pwa_profile_directory",
        "tmux_session_name",
        "tmux_status_bg",
        "tailscale_auth_key",
        "fleet_enroll_secret",
        "fleet_end_user_email",
        "workstation_hostname",
    ]:
        if key in config:
            write_scalar(lines, key, config[key])

    return "\n".join(lines) + "\n"


def write_local_yml(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    path.chmod(0o600)
    return path


def build_config(profile, selected, unmanaged_casks=()):
    if profile == "macos":
        return build_macos_config(selected, unmanaged_casks)
    config = {
        "install_packages": True,
        "install_snap_apps": profile == "ubuntu",
        "install_flatpak_apps": profile == "fedora_asahi",
        "configure_ssh": False,
        "configure_gnome": profile == "ubuntu",
        "configure_kde": profile == "fedora_asahi",
        "configure_desktop_shortcuts": False,
        "apt_google_chrome_enabled": profile == "ubuntu" and "chrome" in selected,
        "dnf_install_allowerasing": profile == "fedora_asahi",
    }
    for app in APPS:
        for flag in app_flags(app):
            config[flag] = app["key"] in selected

    apt_packages = []
    dnf_packages = []
    snap_packages = []
    flatpak_packages = []
    apt_foreign_architectures = []
    rpmfusion = False

    for app in APPS:
        if app["key"] not in selected:
            continue
        apt_packages += app.get("apt", [])
        dnf_packages += app.get("dnf", [])
        snap_packages += app.get("snap", [])
        flatpak_packages += app.get("flatpak", [])
        apt_foreign_architectures += app.get("foreign_arch", [])
        rpmfusion = rpmfusion or app.get("rpmfusion", False)

    config["install_flatpak_apps"] = profile == "fedora_asahi" or bool(flatpak_packages)

    if profile in APT_PROFILES:
        if profile == "ubuntu_server":
            apt_packages += ["openssh-server"]
        config["apt_packages"] = unique(apt_packages)
        config["apt_foreign_architectures"] = unique(apt_foreign_architectures)
        if flatpak_packages:
            config["flatpak_packages"] = unique(flatpak_packages)
        if profile == "ubuntu":
            config["snap_packages"] = unique(snap_packages)
    else:
        config["dnf_packages"] = unique(dnf_packages)
        config["flatpak_packages"] = unique(flatpak_packages)
        config["rpmfusion_release_packages"] = [
            "https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-{{ ansible_facts['distribution_major_version'] }}.noarch.rpm",
            "https://mirrors.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-{{ ansible_facts['distribution_major_version'] }}.noarch.rpm",
        ] if rpmfusion else []

    return config


def build_macos_config(selected, unmanaged_casks=()):
    config = {"install_packages": True, "configure_ssh": False}
    for app in visible_apps("macos"):
        for flag in app_flags(app):
            config[flag] = app["key"] in selected
    chosen = [app for app in APPS if app["key"] in selected and app_visible(app, "macos")]
    config["brew_packages"] = unique(name for app in chosen for name in app.get("brew", []))
    # Apps already in /Applications from outside Homebrew are reported, not
    # installed: running `brew install --cask` would download the installer
    # before failing on the existing app.
    config["brew_casks"] = unique(
        name
        for app in chosen
        if app["key"] not in unmanaged_casks
        for name in app.get("cask", [])
    )
    config["brew_casks_present"] = unique(
        name
        for app in chosen
        if app["key"] in unmanaged_casks
        for name in app.get("cask", [])
    )
    return config


PROFILE_LABELS = {
    "ubuntu": "Ubuntu GNOME",
    "ubuntu_server": "Ubuntu Server (remote agent box)",
    "fedora_asahi": "Fedora Asahi Remix KDE",
    "macos": "macOS",
}


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Chinook workstation configurator")
    parser.add_argument(
        "--profile",
        choices=list(PLAYBOOKS),
        help="Skip the profile prompt (used by the one-line installer after OS detection)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=LOCAL_VARS,
        help="Path to write local.yml (default: ansible/group_vars/local.yml)",
    )
    parser.add_argument(
        "--no-detect",
        action="store_true",
        help="Don't tick the apps already installed on this machine",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    print("Chinook workstation configurator")
    try:
        if args.profile:
            profile = args.profile
            print(f"\nUsing detected profile: {PROFILE_LABELS[profile]}")
        else:
            profile = choose_one(
                "Select a setup profile",
                list(PROFILE_LABELS.items()),
            )

        apps = visible_apps(profile)
        installed, unmanaged_casks = (set(), set()) if args.no_detect else detect_installation(profile)
        previous = read_local_yml(args.output)
        if previous is not None:
            # A re-run starts from the last answers, so it doesn't bring back
            # apps that were unticked before.
            initial = previous_selection(profile, previous)
        else:
            initial = default_selection(profile)
        if installed:
            print("\nApps already on this machine are ticked and marked (installed).")
            print("Unticking one makes Chinook stop managing it; it doesn't uninstall it.")
        choices = [
            dict(app, label=app_label(app, profile) + (" (installed)" if app["key"] in installed else ""))
            for app in apps
        ]
        selected = choose_many("Select apps and modules", choices, initial | installed)
        config = build_config(profile, selected, unmanaged_casks)
        saved = previous or {}

        def saved_text(key, default=""):
            value = saved.get(key)
            return value if isinstance(value, str) and value else default

        if ask_yes_no("Configure SSH snippets", False):
            config["configure_ssh"] = True
            host = ask("SSH host alias", "github.com")
            hostname = ask("SSH hostname", host)
            identity = ask("SSH identity file", "~/.ssh/id_ed25519_github")
            config["ssh_hosts"] = [{"host": host, "hostname": hostname, "user": "git", "identity_file": identity}]

        if "tmux" in selected:
            while True:
                session_name = ask("tmux session name", saved_text("tmux_session_name", "main"))
                if TMUX_SESSION_NAME_RE.fullmatch(session_name):
                    config["tmux_session_name"] = session_name
                    break
                print("Use only letters, numbers, underscores, or hyphens.")
            config["tmux_status_bg"] = ask("tmux status bar color (colour24, green, red, blue)", saved_text("tmux_status_bg", "colour24"))

        if "tailscale" in selected:
            auth_key = ask("Tailscale auth key (optional, leave empty to join later)", "") or saved_text("tailscale_auth_key")
            if auth_key:
                config["tailscale_auth_key"] = auth_key

        if "fleet" in selected:
            print("\nFleet lists this device by its hostname, in the nombre-apellido format (for example john-doe).")
            while True:
                hostname = ask("Device name", saved_text("workstation_hostname", current_hostname())).lower()
                if HOSTNAME_RE.fullmatch(hostname):
                    break
                print("Use lowercase letters, numbers, and hyphens, like john-doe.")
            if hostname != current_hostname():
                config["workstation_hostname"] = hostname
            if saved_text("fleet_enroll_secret"):
                secret = ask("Fleet enroll secret (leave empty to keep the saved one)", "") or saved_text("fleet_enroll_secret")
            else:
                secret = ask("Fleet enroll secret (from the Fleet admin; leave empty to enroll later)", "")
            if secret:
                config["fleet_enroll_secret"] = secret
            # fleetd on macOS only learns the owner's email through MDM enrollment.
            if profile != "macos":
                email = ask("Your work email for Fleet (optional)", saved_text("fleet_end_user_email"))
                if email:
                    config["fleet_end_user_email"] = email

        if "onedrive" in selected:
            sync_dir = ask("OneDrive sync dir", saved_text("onedrive_sync_dir", "~/OneDrive"))
            sync_items = ask("OneDrive selective sync entries, comma separated", ", ".join(saved.get("onedrive_sync_list") or []))
            config["onedrive_sync_dir"] = sync_dir
            config["onedrive_sync_list"] = [item.strip() for item in sync_items.split(",") if item.strip()]

        if "keychron" in selected:
            config["keychron_vendor_id"] = ask("Keychron vendor ID", saved_text("keychron_vendor_id", "3434"))
            config["keychron_product_id"] = ask("Keychron product ID", saved_text("keychron_product_id", "0240"))

        if "teams_pwa" in selected:
            config["teams_pwa_app_id"] = ask("Teams Chrome app ID", saved_text("teams_pwa_app_id"))
            config["teams_pwa_profile_directory"] = ask("Chrome profile directory", saved_text("teams_pwa_profile_directory", "Default"))

        if profile == "fedora_asahi":
            keep = choose_many(
                "Fedora defaults to keep installed",
                [{"key": item, "label": item} for item in FEDORA_REMOVALS],
                set(),
            )
            config["dnf_remove_packages"] = [item for item in FEDORA_REMOVALS if item not in keep]
    except EOFError:
        print("error: input ended before configuration finished.", file=sys.stderr)
        return 1

    output = write_local_yml(args.output, generate_local_yml(profile, config))
    print(f"\nWrote {output}")
    print(f"Run: ansible-playbook {PLAYBOOKS[profile]} --ask-become-pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
