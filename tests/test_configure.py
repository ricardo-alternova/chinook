#!/usr/bin/env python3
import importlib.util
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
CONFIGURE_PATH = ROOT / "tools" / "configure.py"

spec = importlib.util.spec_from_file_location("chinook_configure", CONFIGURE_PATH)
configure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(configure)

try:
    import yaml
except ImportError:
    yaml = None


def app_index(profile, key):
    keys = [app["key"] for app in configure.visible_apps(profile)]
    return str(keys.index(key) + 1)


def run_tui(args, answers, timeout=8):
    tmp = tempfile.TemporaryDirectory()
    output = Path(tmp.name) / "local.yml"
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    result = subprocess.run(
        [sys.executable, str(CONFIGURE_PATH), *args, "-o", str(output)],
        input="\n".join(answers) + "\n",
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env=env,
        timeout=timeout,
        check=False,
    )
    return result, output, tmp


def parse_yaml(text):
    if yaml is None:
        raise RuntimeError("PyYAML is required: python3 -m pip install pyyaml")
    return yaml.safe_load(text)


class TestCatalog(unittest.TestCase):
    def test_app_keys_are_unique(self):
        keys = [app["key"] for app in configure.APPS]
        self.assertEqual(keys, list(dict.fromkeys(keys)))

    def test_playbooks_exist(self):
        for path in configure.PLAYBOOKS.values():
            self.assertTrue((ROOT / path).is_file(), path)

    def test_flags_are_referenced_by_playbooks(self):
        playbook_text = "\n".join(
            (ROOT / path).read_text(encoding="utf-8") for path in configure.PLAYBOOKS.values()
        )
        for app in configure.APPS:
            flag = app.get("flag")
            if flag:
                self.assertIn(flag, playbook_text, f"{app['key']} flag {flag} missing from playbooks")

    def test_server_hides_desktop_apps(self):
        keys = {app["key"] for app in configure.visible_apps("ubuntu_server")}
        self.assertIn("tmux", keys)
        self.assertIn("opencode_cli", keys)
        self.assertNotIn("kitty", keys)
        self.assertNotIn("opencode_desktop", keys)
        self.assertNotIn("steam", keys)
        self.assertNotIn("grok_bot", keys)

    def test_grok_bot_is_desktop_only(self):
        for profile in ("ubuntu", "fedora_asahi"):
            self.assertIn("grok_bot", {app["key"] for app in configure.visible_apps(profile)})
        playbook_dir = ROOT / "ansible" / "playbooks"
        ubuntu = (playbook_dir / "ubuntu.yml").read_text(encoding="utf-8")
        fedora = (playbook_dir / "fedora_asahi.yml").read_text(encoding="utf-8")
        server = (playbook_dir / "ubuntu_server.yml").read_text(encoding="utf-8")
        self.assertIn("install_grok_bot", ubuntu)
        self.assertIn("install_grok_bot", fedora)
        self.assertNotIn("install_grok_bot", server)
        self.assertTrue((ROOT / "ansible" / "roles" / "grok_bot" / "tasks" / "main.yml").is_file())

    def test_cursor_is_desktop_only(self):
        for profile in ("ubuntu", "fedora_asahi"):
            self.assertIn("cursor", {app["key"] for app in configure.visible_apps(profile)})
        playbook_dir = ROOT / "ansible" / "playbooks"
        ubuntu = (playbook_dir / "ubuntu.yml").read_text(encoding="utf-8")
        fedora = (playbook_dir / "fedora_asahi.yml").read_text(encoding="utf-8")
        server = (playbook_dir / "ubuntu_server.yml").read_text(encoding="utf-8")
        self.assertIn("install_cursor", ubuntu)
        self.assertIn("install_cursor", fedora)
        self.assertNotIn("install_cursor", server)
        self.assertTrue((ROOT / "ansible" / "roles" / "cursor" / "tasks" / "main.yml").is_file())

    def test_desktop_hides_server_defaults_as_optional(self):
        ubuntu_defaults = configure.default_selection("ubuntu")
        server_defaults = configure.default_selection("ubuntu_server")
        self.assertIn("opencode_cli", ubuntu_defaults)
        self.assertIn("opencode_desktop", ubuntu_defaults)
        self.assertIn("tmux", server_defaults)
        self.assertIn("tailscale", server_defaults)
        self.assertNotIn("tmux", ubuntu_defaults)
        self.assertNotIn("opencode_desktop", server_defaults)
        fedora_defaults = configure.default_selection("fedora_asahi")
        self.assertIn("opencode_cli", fedora_defaults)
        self.assertIn("opencode_desktop", fedora_defaults)

    def test_profile_vars_enable_opencode(self):
        ubuntu = (ROOT / "ansible/group_vars/ubuntu.yml").read_text(encoding="utf-8")
        fedora = (ROOT / "ansible/group_vars/fedora_asahi.yml").read_text(encoding="utf-8")
        server = (ROOT / "ansible/group_vars/ubuntu_server.yml").read_text(encoding="utf-8")
        example = (ROOT / "ansible/group_vars/local.yml.example").read_text(encoding="utf-8")
        self.assertIn("install_opencode_cli: true", ubuntu)
        self.assertIn("install_opencode_desktop: true", ubuntu)
        self.assertIn("install_opencode_cli: true", fedora)
        self.assertIn("install_opencode_desktop: true", fedora)
        self.assertIn("install_opencode_cli: true", server)
        self.assertNotIn("install_opencode_desktop: true", server)
        self.assertIn("install_opencode_cli: true", example)
        self.assertIn("install_opencode_desktop: true", example)

    def test_generated_local_yml_overrides_profile_opencode(self):
        def load(name):
            return parse_yaml((ROOT / "ansible/group_vars" / name).read_text(encoding="utf-8"))

        merged = {}
        merged.update(load("all.yml"))
        merged.update(load("ubuntu.yml"))
        self.assertTrue(merged["install_opencode_cli"])
        self.assertTrue(merged["install_opencode_desktop"])
        merged.update({"install_opencode_cli": False, "install_opencode_desktop": False})
        self.assertFalse(merged["install_opencode_cli"])
        self.assertFalse(merged["install_opencode_desktop"])


class TestYamlValue(unittest.TestCase):
    def test_bools_and_plain_scalars(self):
        self.assertEqual(configure.yaml_value(True), "true")
        self.assertEqual(configure.yaml_value(False), "false")
        self.assertEqual(configure.yaml_value(""), '""')
        self.assertEqual(configure.yaml_value("ricardo"), "ricardo")

    def test_quotes_yaml_traps(self):
        self.assertEqual(configure.yaml_value("yes"), '"yes"')
        self.assertEqual(configure.yaml_value("/home/user/My Docs"), '"/home/user/My Docs"')
        self.assertEqual(configure.yaml_value('say "hi"'), '"say \\"hi\\""')
        self.assertTrue(configure.yaml_value("host:port").startswith('"'))
        self.assertTrue(configure.yaml_value("{{ jinja }}").startswith('"'))


class TestBuildConfig(unittest.TestCase):
    def test_ubuntu_defaults(self):
        selected = configure.default_selection("ubuntu")
        config = configure.build_config("ubuntu", selected)
        self.assertTrue(config["configure_gnome"])
        self.assertFalse(config["configure_kde"])
        self.assertTrue(config["install_snap_apps"])
        self.assertFalse(config["install_flatpak_apps"])
        self.assertTrue(config["install_opencode_cli"])
        self.assertTrue(config["install_opencode_desktop"])
        self.assertFalse(config["install_grok_bot"])
        self.assertFalse(config["install_cursor"])
        self.assertFalse(config["configure_tmux"])
        self.assertIn("google-chrome-stable", config["apt_packages"])
        self.assertIn("onlyoffice-desktopeditors", config["snap_packages"])
        self.assertNotIn("dnf_packages", config)

    def test_ubuntu_server_defaults(self):
        selected = configure.default_selection("ubuntu_server")
        config = configure.build_config("ubuntu_server", selected)
        self.assertFalse(config["configure_gnome"])
        self.assertTrue(config["configure_tmux"])
        self.assertTrue(config["install_tailscale"])
        self.assertTrue(config["configure_ufw"])
        self.assertTrue(config["configure_fail2ban"])
        self.assertTrue(config["install_opencode_cli"])
        self.assertFalse(config["install_opencode_desktop"])
        self.assertIn("openssh-server", config["apt_packages"])
        self.assertIn("tmux", config["apt_packages"])
        self.assertNotIn("snap_packages", config)
        self.assertNotIn("kitty", config["apt_packages"])

    def test_fedora_defaults_use_dnf_and_rpmfusion(self):
        selected = configure.default_selection("fedora_asahi")
        config = configure.build_config("fedora_asahi", selected)
        self.assertTrue(config["configure_kde"])
        self.assertTrue(config["install_flatpak_apps"])
        self.assertFalse(config["install_snap_apps"])
        self.assertIn("chromium", config["dnf_packages"])
        self.assertNotIn("google-chrome-stable", config.get("apt_packages", []))
        self.assertTrue(config["rpmfusion_release_packages"])
        self.assertIn("org.onlyoffice.desktopeditors", config["flatpak_packages"])
        self.assertTrue(config["install_opencode_cli"])
        self.assertTrue(config["install_opencode_desktop"])


class TestGenerateLocalYml(unittest.TestCase):
    def test_roundtrip_and_mode(self):
        selected = configure.default_selection("ubuntu")
        config = configure.build_config("ubuntu", selected)
        text = configure.generate_local_yml("ubuntu", "yes", "/home/user/My Docs", config)
        data = parse_yaml(text)
        self.assertEqual(data["profile"], "ubuntu")
        self.assertEqual(data["workstation_user"], "yes")
        self.assertEqual(data["workstation_home"], "/home/user/My Docs")
        self.assertTrue(data["install_opencode_cli"])
        with tempfile.TemporaryDirectory() as tmp:
            path = configure.write_local_yml(Path(tmp) / "local.yml", text)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_ssh_and_tailscale_values(self):
        config = configure.build_config("ubuntu_server", configure.default_selection("ubuntu_server"))
        config["configure_ssh"] = True
        config["ssh_hosts"] = [
            {
                "host": "github.com",
                "hostname": "ssh.github.com",
                "user": "git",
                "identity_file": "~/.ssh/id with spaces",
            }
        ]
        config["tailscale_auth_key"] = "tskey-auth-abc:def"
        text = configure.generate_local_yml("ubuntu_server", "ricardo", "/home/ricardo", config)
        data = parse_yaml(text)
        self.assertEqual(data["ssh_hosts"][0]["identity_file"], "~/.ssh/id with spaces")
        self.assertEqual(data["tailscale_auth_key"], "tskey-auth-abc:def")


class TestPrompts(unittest.TestCase):
    def test_choose_one_rejects_then_accepts(self):
        with patch("builtins.input", side_effect=["0", "9", "2"]):
            choice = configure.choose_one("Pick", [("a", "A"), ("b", "B")])
        self.assertEqual(choice, "b")

    def test_choose_many_toggle_all_none_and_invalid(self):
        apps = [{"key": "one", "label": "One"}, {"key": "two", "label": "Two"}]
        with patch("builtins.input", side_effect=["nope", "n", "1,2", "2", "a", ""]):
            selected = configure.choose_many("Apps", apps, {"one"})
        self.assertEqual(selected, {"one", "two"})

    def test_ask_yes_no_defaults(self):
        with patch("builtins.input", side_effect=["", "n", "yes"]):
            self.assertTrue(configure.ask_yes_no("Continue", True))
            self.assertFalse(configure.ask_yes_no("Continue", True))
            self.assertTrue(configure.ask_yes_no("Continue", False))


class TestTuiProcess(unittest.TestCase):
    def run_tui(self, args, answers, timeout=8):
        result, output, tmp = run_tui(args, answers, timeout)
        self.addCleanup(tmp.cleanup)
        return result, output

    def test_help(self):
        result = subprocess.run(
            [sys.executable, str(CONFIGURE_PATH), "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("--profile", result.stdout)

    def test_eof_exits_before_writing(self):
        result, output = self.run_tui(["--profile", "ubuntu"], [])
        self.assertEqual(result.returncode, 1)
        self.assertIn("input ended before configuration finished", result.stderr)
        self.assertFalse(output.exists())

    def test_ubuntu_defaults_via_stdin(self):
        result, output = self.run_tui(
            ["--profile", "ubuntu"],
            ["ricardo", "/home/ricardo", "", ""],
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertTrue(output.exists())
        data = parse_yaml(output.read_text(encoding="utf-8"))
        self.assertEqual(data["profile"], "ubuntu")
        self.assertEqual(data["workstation_user"], "ricardo")
        self.assertTrue(data["configure_gnome"])
        self.assertTrue(data["install_opencode_cli"])
        self.assertTrue(data["install_opencode_desktop"])
        self.assertIn("Wrote", result.stdout)
        self.assertIn("ansible/playbooks/ubuntu.yml", result.stdout)

    def test_ubuntu_without_preset_profile_choice(self):
        result, output = self.run_tui(
            [],
            ["1", "ricardo", "/home/ricardo", "", ""],
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        data = parse_yaml(output.read_text(encoding="utf-8"))
        self.assertEqual(data["profile"], "ubuntu")

    def test_ubuntu_server_extra_prompts(self):
        result, output = self.run_tui(
            ["--profile", "ubuntu_server"],
            [
                "agent",
                "/home/agent",
                "",
                "",
                "not a valid session",
                "devbox",
                "green",
                "",
            ],
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        data = parse_yaml(output.read_text(encoding="utf-8"))
        self.assertEqual(data["profile"], "ubuntu_server")
        self.assertTrue(data["configure_tmux"])
        self.assertEqual(data["tmux_session_name"], "devbox")
        self.assertEqual(data["tmux_status_bg"], "green")
        self.assertNotIn("tailscale_auth_key", data)
        self.assertIn("openssh-server", data["apt_packages"])
        self.assertNotIn("snap_packages", data)

    def test_fedora_removals_keep_one(self):
        result, output = self.run_tui(
            ["--profile", "fedora_asahi"],
            ["ricardo", "/home/ricardo", "", "", "1", ""],
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        data = parse_yaml(output.read_text(encoding="utf-8"))
        self.assertEqual(data["profile"], "fedora_asahi")
        self.assertTrue(data["configure_kde"])
        kept = configure.FEDORA_REMOVALS[0]
        self.assertNotIn(kept, data["dnf_remove_packages"])
        self.assertIn(configure.FEDORA_REMOVALS[1], data["dnf_remove_packages"])

    def test_optional_prompts_onedrive_ssh_and_toggle(self):
        onedrive = app_index("ubuntu", "onedrive")
        result, output = self.run_tui(
            ["--profile", "ubuntu"],
            [
                "ricardo",
                "/home/ricardo",
                onedrive,
                "",
                "y",
                "gitlab.com",
                "",
                "~/.ssh/id_ed25519_gitlab",
                "~/OneDrive/Work",
                "Documents, Photos",
            ],
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        data = parse_yaml(output.read_text(encoding="utf-8"))
        self.assertTrue(data["install_onedrive"])
        self.assertTrue(data["configure_ssh"])
        self.assertEqual(data["ssh_hosts"][0]["host"], "gitlab.com")
        self.assertEqual(data["ssh_hosts"][0]["hostname"], "gitlab.com")
        self.assertEqual(data["onedrive_sync_dir"], "~/OneDrive/Work")
        self.assertEqual(data["onedrive_sync_list"], ["Documents", "Photos"])


class TestInstallScript(unittest.TestCase):
    def test_bash_syntax(self):
        result = subprocess.run(
            ["bash", "-n", str(ROOT / "install")],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_next_steps_copy(self):
        text = (ROOT / "install").read_text(encoding="utf-8")
        self.assertIn("Open OpenCode and set up your credentials", text)
        self.assertIn("opencode auth login", text)
        self.assertIn("GitHub / GitLab accounts", text)
        self.assertNotIn("after-provisioning-manual-steps", text)

    def test_ubuntu_profile_override_rejects_fedora(self):
        text = (ROOT / "install").read_text(encoding="utf-8")
        self.assertIn("On Ubuntu, CHINOOK_PROFILE must be ubuntu or ubuntu_server", text)


if __name__ == "__main__":
    unittest.main()
