#!/usr/bin/env python3
from pathlib import Path
import getpass
import re


ROOT = Path(__file__).resolve().parents[1]
LOCAL_VARS = ROOT / "ansible" / "group_vars" / "local.yml"


DESKTOP_PROFILES = ("ubuntu", "fedora_asahi")
APT_PROFILES = ("ubuntu", "ubuntu_server")
PLAYBOOKS = {
    "ubuntu": "ansible/playbooks/ubuntu.yml",
    "ubuntu_server": "ansible/playbooks/ubuntu_server.yml",
    "fedora_asahi": "ansible/playbooks/fedora_asahi.yml",
}

APPS = [
    {
        "key": "base_cli",
        "label": "Base CLI tools",
        "default": True,
        "apt": ["ansible", "curl", "git", "jq"],
        "dnf": ["ansible", "git", "jq", "curl"],
    },
    {
        "key": "shell",
        "label": "Zsh, Starship, and zsh plugins",
        "default": True,
        "apt": ["starship", "zsh", "zsh-autosuggestions", "zsh-syntax-highlighting"],
        "dnf": ["starship", "zsh", "zsh-autosuggestions", "zsh-syntax-highlighting"],
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
        "apt": ["btop"],
        "dnf": ["btop"],
    },
    {
        "key": "gh",
        "label": "GitHub CLI",
        "default_profiles": ["ubuntu_server"],
        "apt": ["gh"],
        "dnf": ["gh"],
    },
    {
        "key": "tailscale",
        "label": "Tailscale (install only; join is manual)",
        "default_profiles": ["ubuntu_server"],
        "flag": "install_tailscale",
    },
    {
        "key": "ufw",
        "label": "UFW firewall (deny inbound, allow SSH)",
        "default_profiles": ["ubuntu_server"],
        "flag": "configure_ufw",
    },
    {
        "key": "fail2ban",
        "label": "fail2ban (ban repeated SSH failures)",
        "default_profiles": ["ubuntu_server"],
        "flag": "configure_fail2ban",
    },
    {"key": "kitty", "label": "Kitty terminal", "default": True, "profiles": DESKTOP_PROFILES, "apt": ["kitty"], "dnf": ["kitty"]},
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
        "apt": ["heif-gdk-pixbuf", "heif-thumbnailer", "libheif-examples", "libheif-plugins-all"],
    },
    {"key": "flameshot", "label": "Flameshot", "default": True, "profiles": DESKTOP_PROFILES, "apt": ["flameshot"], "dnf": ["flameshot"]},
    {"key": "chrome", "label": "Google Chrome on Ubuntu / Chromium on Fedora Asahi", "default": True, "profiles": DESKTOP_PROFILES, "apt": ["google-chrome-stable"], "dnf": ["chromium"]},
    {"key": "gimp", "label": "GIMP", "default": False, "profiles": DESKTOP_PROFILES, "apt": ["gimp"], "dnf": ["gimp"]},
    {"key": "xournalpp", "label": "Xournal++", "default": False, "profiles": DESKTOP_PROFILES, "apt": ["xournalpp"], "dnf": ["xournalpp"]},
    {"key": "onedrive", "label": "OneDrive", "default": False, "apt": ["onedrive"], "dnf": ["onedrive"], "flag": "install_onedrive"},
    {"key": "mangohud", "label": "MangoHud", "default": False, "profiles": DESKTOP_PROFILES, "apt": ["mangohud"], "dnf": ["mangohud"], "flag": "install_mangohud"},
    {"key": "obs_studio", "label": "OBS Studio", "default": False, "profiles": DESKTOP_PROFILES, "apt": ["obs-studio"], "dnf": ["obs-studio"]},
    {"key": "opencode_cli", "label": "OpenCode CLI", "default": False, "flag": "install_opencode_cli"},
    {"key": "opencode_desktop", "label": "OpenCode Desktop (x86_64 Linux only)", "default": False, "profiles": DESKTOP_PROFILES, "flag": "install_opencode_desktop"},
    {"key": "codex_cli", "label": "Codex CLI", "default": False, "flag": "install_codex_cli"},
    {"key": "t3_code", "label": "T3 Code (remote agent control surface)", "default": False, "flag": "install_t3_code"},
    {"key": "steam", "label": "Steam", "default": False, "profiles": DESKTOP_PROFILES, "apt": ["steam-installer"], "foreign_arch": ["i386"]},
    {"key": "discord", "label": "Discord", "default": False, "profiles": DESKTOP_PROFILES, "snap": ["discord"], "flatpak": ["com.discordapp.Discord"]},
    {"key": "onlyoffice", "label": "OnlyOffice", "default": True, "profiles": DESKTOP_PROFILES, "snap": ["onlyoffice-desktopeditors"], "flatpak": ["org.onlyoffice.desktopeditors"]},
    {"key": "spotify", "label": "Spotify", "default": False, "profiles": DESKTOP_PROFILES, "snap": ["spotify"], "flatpak": ["com.spotify.Client"]},
    {"key": "localsend", "label": "LocalSend", "default": True, "profiles": DESKTOP_PROFILES, "snap": ["localsend"], "flatpak": ["org.localsend.localsend_app"]},
    {"key": "zapzap", "label": "ZapZap", "default": False, "profiles": DESKTOP_PROFILES, "snap": ["zapzap"]},
    {"key": "zed", "label": "Zed editor", "default": True, "profiles": DESKTOP_PROFILES, "flag": "install_zed"},
    {"key": "balena_etcher", "label": "Balena Etcher", "default": False, "profiles": DESKTOP_PROFILES, "flag": "install_balena_etcher"},
    {"key": "teams_pwa", "label": "Microsoft Teams PWA", "default": False, "profiles": DESKTOP_PROFILES, "flag": "configure_teams_pwa"},
    {"key": "keychron", "label": "Keychron udev rule", "default": False, "flag": "configure_keychron"},
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
        for part in value.replace(",", " ").split():
            if part.isdigit() and 1 <= int(part) <= len(choices):
                key = choices[int(part) - 1]["key"]
                if key in selected:
                    selected.remove(key)
                else:
                    selected.add(key)


def yaml_value(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if value == "":
        return '""'
    if any(char in value for char in [":", "#", "{", "}", "[", "]", "*", "&", "<", ">"]):
        return '"' + value.replace('"', '\\"') + '"'
    return value


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


def app_visible(app, profile):
    profiles = app.get("profiles")
    return profiles is None or profile in profiles


def app_default(app, profile):
    if "default_profiles" in app:
        return profile in app["default_profiles"]
    return app.get("default", False)


def build_config(profile, selected):
    config = {
        "install_packages": True,
        "install_snap_apps": profile == "ubuntu",
        "install_flatpak_apps": profile == "fedora_asahi",
        "install_onedrive": "onedrive" in selected,
        "install_mangohud": "mangohud" in selected,
        "install_opencode_cli": "opencode_cli" in selected,
        "install_opencode_desktop": "opencode_desktop" in selected,
        "install_codex_cli": "codex_cli" in selected,
        "install_t3_code": "t3_code" in selected,
        "install_zed": "zed" in selected,
        "install_balena_etcher": "balena_etcher" in selected,
        "install_tailscale": "tailscale" in selected,
        "configure_timeshift": True,
        "configure_ssh": False,
        "configure_gnome": profile == "ubuntu",
        "configure_kde": profile == "fedora_asahi",
        "configure_tmux": "tmux" in selected,
        "configure_ufw": "ufw" in selected,
        "configure_fail2ban": "fail2ban" in selected,
        "configure_keychron": "keychron" in selected,
        "configure_teams_pwa": "teams_pwa" in selected,
        "configure_desktop_shortcuts": False,
        "apt_google_chrome_enabled": profile == "ubuntu" and "chrome" in selected,
        "dnf_install_allowerasing": profile == "fedora_asahi",
    }

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

    if profile in APT_PROFILES:
        if profile == "ubuntu_server":
            apt_packages += ["openssh-server"]
        config["apt_packages"] = unique(apt_packages)
        config["apt_foreign_architectures"] = unique(apt_foreign_architectures)
        if profile == "ubuntu":
            config["snap_packages"] = unique(snap_packages)
    else:
        config["dnf_packages"] = unique(dnf_packages)
        config["flatpak_packages"] = unique(flatpak_packages)
        config["rpmfusion_release_packages"] = [
            "https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-{{ ansible_distribution_major_version }}.noarch.rpm",
            "https://mirrors.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-{{ ansible_distribution_major_version }}.noarch.rpm",
        ] if rpmfusion else []

    return config


def main():
    print("Chinook workstation configurator")
    profile = choose_one(
        "Select a setup profile",
        [
            ("ubuntu", "Ubuntu GNOME"),
            ("ubuntu_server", "Ubuntu Server (remote agent box)"),
            ("fedora_asahi", "Fedora Asahi Remix KDE"),
        ],
    )

    user = ask("Workstation user", getpass.getuser())
    home = ask("Workstation home", str(Path.home()))
    visible_apps = [item for item in APPS if app_visible(item, profile)]
    default_apps = {item["key"] for item in visible_apps if app_default(item, profile)}
    selected = choose_many("Select apps and modules", visible_apps, default_apps)
    config = build_config(profile, selected)

    if ask_yes_no("Configure SSH snippets", False):
        config["configure_ssh"] = True
        host = ask("SSH host alias", "github.com")
        hostname = ask("SSH hostname", host)
        identity = ask("SSH identity file", "~/.ssh/id_ed25519_github")
        config["ssh_hosts"] = [{"host": host, "hostname": hostname, "user": "git", "identity_file": identity}]

    if "tmux" in selected:
        while True:
            session_name = ask("tmux session name", "main")
            if re.fullmatch(r"[A-Za-z0-9_-]+", session_name):
                config["tmux_session_name"] = session_name
                break
            print("Use only letters, numbers, underscores, or hyphens.")
        config["tmux_status_bg"] = ask("tmux status bar color (colour24, green, red, blue)", "colour24")

    if "tailscale" in selected:
        auth_key = ask("Tailscale auth key (optional, leave empty to join later)", "")
        if auth_key:
            config["tailscale_auth_key"] = auth_key

    if "onedrive" in selected:
        sync_dir = ask("OneDrive sync dir", "~/OneDrive")
        sync_items = ask("OneDrive selective sync entries, comma separated", "")
        config["onedrive_sync_dir"] = sync_dir
        config["onedrive_sync_list"] = [item.strip() for item in sync_items.split(",") if item.strip()]

    if "keychron" in selected:
        config["keychron_vendor_id"] = ask("Keychron vendor ID", "3434")
        config["keychron_product_id"] = ask("Keychron product ID", "0240")

    if "teams_pwa" in selected:
        config["teams_pwa_app_id"] = ask("Teams Chrome app ID")
        config["teams_pwa_profile_directory"] = ask("Chrome profile directory", "Default")

    if profile == "fedora_asahi":
        keep = choose_many(
            "Fedora defaults to keep installed",
            [{"key": item, "label": item} for item in FEDORA_REMOVALS],
            set(),
        )
        config["dnf_remove_packages"] = [item for item in FEDORA_REMOVALS if item not in keep]

    lines = ["# Generated by tools/configure.py", f"profile: {profile}"]
    write_scalar(lines, "workstation_user", user)
    write_scalar(lines, "workstation_home", home)
    lines.append("")

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
    ]:
        if key in config:
            write_scalar(lines, key, config[key])

    LOCAL_VARS.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nWrote {LOCAL_VARS}")
    print(f"Run: ansible-playbook {PLAYBOOKS[profile]} --ask-become-pass")


if __name__ == "__main__":
    main()
