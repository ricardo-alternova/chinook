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


def run_tui(args, answers, timeout=8, existing=None):
    tmp = tempfile.TemporaryDirectory()
    output = Path(tmp.name) / "local.yml"
    if existing is not None:
        output.write_text(existing, encoding="utf-8")
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    result = subprocess.run(
        [sys.executable, str(CONFIGURE_PATH), *args, "--no-detect", "-o", str(output)],
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
            for flag in configure.app_flags(app):
                self.assertIn(flag, playbook_text, f"{app['key']} flag {flag} missing from playbooks")

    def test_server_hides_desktop_apps(self):
        keys = {app["key"] for app in configure.visible_apps("ubuntu_server")}
        self.assertIn("tmux", keys)
        self.assertIn("opencode_cli", keys)
        self.assertNotIn("kitty", keys)
        self.assertNotIn("opencode_desktop", keys)
        self.assertNotIn("steam", keys)
        self.assertNotIn("grok_bot", keys)
        self.assertNotIn("wayshot", keys)
        self.assertNotIn("input_remapper", keys)

    def test_fedora_uses_firewalld_not_ufw(self):
        fedora = (ROOT / "ansible/playbooks/fedora_asahi.yml").read_text(encoding="utf-8")
        self.assertIn("role: firewalld", fedora)
        self.assertNotIn("role: ufw", fedora)
        role = (ROOT / "ansible/roles/firewalld/tasks/main.yml").read_text(encoding="utf-8")
        self.assertIn("firewall-cmd", role)
        self.assertIn("name: ufw", role)
        self.assertIn("state: absent", role)
        for profile in ("ubuntu", "ubuntu_server"):
            playbook = (ROOT / "ansible/playbooks" / f"{profile}.yml").read_text(encoding="utf-8")
            self.assertIn("role: ufw", playbook)
            self.assertIn("ufw", {app["key"] for app in configure.visible_apps(profile)})
        self.assertNotIn("ufw", {app["key"] for app in configure.visible_apps("fedora_asahi")})

    def test_timeshift_is_a_selectable_linux_module(self):
        for profile in configure.LINUX_PROFILES:
            keys = {app["key"] for app in configure.visible_apps(profile)}
            self.assertIn("timeshift", keys, profile)
            self.assertIn("timeshift", configure.default_selection(profile), profile)
            self.assertTrue(configure.build_config(profile, configure.default_selection(profile))["configure_timeshift"], profile)
            without = configure.default_selection(profile) - {"timeshift"}
            self.assertFalse(configure.build_config(profile, without)["configure_timeshift"], profile)
        self.assertNotIn("timeshift", {app["key"] for app in configure.visible_apps("macos")})

    def test_input_remapper_is_desktop_only(self):
        for profile in ("ubuntu", "fedora_asahi"):
            self.assertIn("input_remapper", {app["key"] for app in configure.visible_apps(profile)})
        selected = configure.default_selection("ubuntu")
        selected.add("input_remapper")
        config = configure.build_config("ubuntu", selected)
        self.assertIn("input-remapper", config["apt_packages"])
        fedora_config = configure.build_config("fedora_asahi", configure.default_selection("fedora_asahi") | {"input_remapper"})
        self.assertIn("input-remapper", fedora_config["dnf_packages"])

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
        self.assertNotIn("install_cursor |", server)
        self.assertTrue((ROOT / "ansible" / "roles" / "cursor" / "tasks" / "main.yml").is_file())

    def test_agent_and_git_clis_on_every_linux_profile(self):
        for profile in configure.LINUX_PROFILES:
            playbook = configure.PLAYBOOKS[profile]
            selected = configure.default_selection(profile)
            config = configure.build_config(profile, selected)
            playbook_text = (ROOT / playbook).read_text(encoding="utf-8")
            for key in ("claude_code", "cursor_cli", "glab"):
                self.assertIn(key, selected, profile)
                self.assertTrue(config[f"install_{key}"], profile)
                self.assertIn(f"role: {key}", playbook_text, profile)
                self.assertTrue((ROOT / "ansible" / "roles" / key / "tasks" / "main.yml").is_file())
            profile_vars = parse_yaml((ROOT / "ansible/group_vars" / f"{profile}.yml").read_text(encoding="utf-8"))
            for flag in ("install_claude_code", "install_cursor_cli", "install_glab", "install_starship"):
                self.assertTrue(profile_vars[flag], f"{profile} {flag}")

    def test_docker_on_every_linux_profile_from_dockers_repos(self):
        role_text = (ROOT / "ansible/roles/docker/tasks/main.yml").read_text(encoding="utf-8")
        all_vars = parse_yaml((ROOT / "ansible/group_vars/all.yml").read_text(encoding="utf-8"))
        for profile in configure.LINUX_PROFILES:
            playbook = configure.PLAYBOOKS[profile]
            config = configure.build_config(profile, configure.default_selection(profile))
            self.assertTrue(config["install_docker"], profile)
            self.assertIn("role: docker", (ROOT / playbook).read_text(encoding="utf-8"), profile)
            profile_vars = parse_yaml((ROOT / "ansible/group_vars" / f"{profile}.yml").read_text(encoding="utf-8"))
            self.assertTrue(profile_vars["install_docker"], profile)
        self.assertIn("docker-compose-plugin", all_vars["docker_packages"])
        self.assertTrue(all_vars["docker_apt_repo_url"].startswith("https://download.docker.com/"))
        self.assertTrue(all_vars["docker_dnf_repo_url"].startswith("https://download.docker.com/"))
        self.assertIn("groups: docker", role_text)

    def test_fleet_on_every_profile_without_a_committed_secret(self):
        all_vars = parse_yaml((ROOT / "ansible/group_vars/all.yml").read_text(encoding="utf-8"))
        self.assertEqual(all_vars["fleet_enroll_secret"], "")
        self.assertEqual(all_vars["fleet_url"], "https://fleet.alternova.dev")
        for profile, playbook in configure.PLAYBOOKS.items():
            config = configure.build_config(profile, configure.default_selection(profile))
            # macOS is the exception: Fleet is the one app ticked by default there.
            self.assertEqual(config["install_fleet"], profile == "macos", profile)
            self.assertIn("fleet", [app["key"] for app in configure.visible_apps(profile)], profile)
            profile_vars = parse_yaml((ROOT / "ansible/group_vars" / f"{profile}.yml").read_text(encoding="utf-8"))
            if profile == "macos":
                self.assertTrue(profile_vars["install_fleet"], profile)
            else:
                self.assertNotIn("install_fleet", profile_vars, profile)
            playbook_text = (ROOT / playbook).read_text(encoding="utf-8")
            self.assertIn("role: fleet", playbook_text, profile)
            self.assertLess(playbook_text.index("role: hostname"), playbook_text.index("role: fleet"), profile)
        tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
        self.assertNotIn("ansible/group_vars/local.yml", tracked)
        enroll = (ROOT / "ansible/roles/fleet/tasks/enroll.yml").read_text(encoding="utf-8")
        # The secret is passed to fleetctl, so that task must not log, and the built package must be deleted.
        build = enroll[enroll.index("- name: Build the fleetd package"):enroll.index("- name: Fail when the fleetd package build fails")]
        self.assertIn("no_log: true", build)
        self.assertIn("always:", enroll)
        self.assertIn("secret-orbit-node-key.txt", enroll)

    def test_compai_agent_is_selectable_everywhere_but_gated(self):
        for profile in configure.LINUX_PROFILES:
            self.assertNotIn("compai_agent", configure.default_selection(profile), profile)
            self.assertIn("compai_agent", {app["key"] for app in configure.visible_apps(profile)}, profile)
        self.assertNotIn("compai_agent", {app["key"] for app in configure.visible_apps("macos")})
        for playbook in ("ubuntu.yml", "ubuntu_server.yml", "fedora_asahi.yml"):
            text = (ROOT / "ansible/playbooks" / playbook).read_text(encoding="utf-8")
            self.assertIn("role: compai_agent", text, playbook)
            self.assertIn("ansible_facts['pkg_mgr'] == 'apt'", text, playbook)
            self.assertIn("ansible_facts['architecture'] == 'x86_64'", text, playbook)
            self.assertIn("configure_gnome | bool", text, playbook)
        loader = (ROOT / "ansible/playbooks/tasks/load_local_vars.yml").read_text(encoding="utf-8")
        self.assertIn("only available for Ubuntu GNOME on amd64", loader)
        role = (ROOT / "ansible/roles/compai_agent/tasks/main.yml").read_text(encoding="utf-8")
        self.assertIn(".config/autostart/comp-ai-device-agent.desktop", role)
        self.assertIn("minlen", role)

    def test_starship_uses_installer_not_distro_packages(self):
        # Ubuntu LTS has no starship APT package; one missing package fails the whole apt task.
        for profile in configure.LINUX_PROFILES:
            config = configure.build_config(profile, configure.default_selection(profile))
            self.assertTrue(config["install_starship"], profile)
            self.assertNotIn("starship", config.get("apt_packages", []), profile)
            self.assertNotIn("starship", config.get("dnf_packages", []), profile)
            profile_vars = parse_yaml((ROOT / "ansible/group_vars" / f"{profile}.yml").read_text(encoding="utf-8"))
            self.assertNotIn("starship", profile_vars.get("apt_packages", []), profile)
            self.assertNotIn("starship", profile_vars.get("dnf_packages", []), profile)
        self.assertTrue((ROOT / "ansible/roles/starship/tasks/main.yml").is_file())

    def test_unity_hub_is_ubuntu_desktop_only(self):
        self.assertIn("unity_hub", {app["key"] for app in configure.visible_apps("ubuntu")})
        for profile in ("ubuntu_server", "fedora_asahi"):
            self.assertNotIn("unity_hub", {app["key"] for app in configure.visible_apps(profile)})
        config = configure.build_config("ubuntu", configure.default_selection("ubuntu") | {"unity_hub"})
        self.assertTrue(config["install_unity_hub"])
        playbook_dir = ROOT / "ansible" / "playbooks"
        self.assertIn("install_unity_hub", (playbook_dir / "ubuntu.yml").read_text(encoding="utf-8"))
        self.assertNotIn("install_unity_hub", (playbook_dir / "ubuntu_server.yml").read_text(encoding="utf-8"))
        self.assertNotIn("install_unity_hub", (playbook_dir / "fedora_asahi.yml").read_text(encoding="utf-8"))
        self.assertTrue((ROOT / "ansible/roles/unity_hub/tasks/main.yml").is_file())
        # Must match the unityhub postinst, or apt fails with conflicting Signed-By values.
        all_vars = parse_yaml((ROOT / "ansible/group_vars/all.yml").read_text(encoding="utf-8"))
        self.assertEqual(all_vars["unity_hub_apt_key_path"], "/usr/share/keyrings/Unity_Technologies_ApS.gpg")
        self.assertEqual(all_vars["unity_hub_apt_sources_path"], "/etc/apt/sources.list.d/unityhub.sources")
        unity_role = (ROOT / "ansible/roles/unity_hub/tasks/main.yml").read_text(encoding="utf-8")
        self.assertIn("/etc/apt/sources.list.d/unityhub.list", unity_role)
        self.assertNotIn("apt_repository", unity_role)

    def test_ansible_yaml_has_no_bare_boolean_words_in_lists(self):
        # A bare `on` in an argv list is parsed as True (ufw allow in True tailscale0).
        import re
        bare = re.compile(r"^\s*-\s+(on|off|yes|no|y|n)\s*$", re.IGNORECASE)
        for path in (ROOT / "ansible").rglob("*.yml"):
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                self.assertIsNone(bare.match(line), f"{path.relative_to(ROOT)}:{number} quote this list item")

    def test_playbooks_always_configure_the_running_account(self):
        loader = parse_yaml((ROOT / "ansible/playbooks/tasks/load_local_vars.yml").read_text(encoding="utf-8"))
        include_index = next(i for i, task in enumerate(loader) if "ansible.builtin.include_vars" in task)
        set_facts = [(i, task["ansible.builtin.set_fact"]) for i, task in enumerate(loader) if "ansible.builtin.set_fact" in task]
        self.assertTrue(any(
            i > include_index
            and facts.get("workstation_user") == "{{ ansible_facts['user_id'] }}"
            and facts.get("workstation_home") == "{{ ansible_facts['env']['HOME'] }}"
            and facts.get("workstation_group") == "{{ ansible_facts['user_gid'] }}"
            for i, facts in set_facts
        ))
        example = (ROOT / "ansible/group_vars/local.yml.example").read_text(encoding="utf-8")
        self.assertNotIn("workstation_user:", example)
        self.assertNotIn("workstation_home:", example)

    def test_shell_and_kitty_are_configured(self):
        for profile in configure.LINUX_PROFILES:
            config = configure.build_config(profile, configure.default_selection(profile))
            self.assertTrue(config["install_starship"], profile)
            self.assertTrue(config["configure_shell"], profile)
            playbook = (ROOT / configure.PLAYBOOKS[profile]).read_text(encoding="utf-8")
            self.assertIn("role: shell", playbook)
            profile_vars = parse_yaml((ROOT / "ansible/group_vars" / f"{profile}.yml").read_text(encoding="utf-8"))
            self.assertTrue(profile_vars["configure_shell"], profile)
            if profile in configure.DESKTOP_PROFILES:
                self.assertTrue(config["configure_kitty"], profile)
                self.assertIn("role: kitty", playbook)
                self.assertTrue(profile_vars["configure_kitty"], profile)
            else:
                self.assertNotIn("role: kitty", playbook)
        shell_role = (ROOT / "ansible/roles/shell/tasks/main.yml").read_text(encoding="utf-8")
        self.assertIn("starship init zsh", shell_role)
        self.assertIn("ansible.builtin.user", shell_role)
        self.assertTrue((ROOT / "ansible/roles/shell/files/starship.toml").is_file())
        kitty_conf = (ROOT / "ansible/roles/kitty/files/kitty.conf").read_text(encoding="utf-8")
        self.assertIn("include catppuccin-mocha.conf", kitty_conf)
        self.assertTrue((ROOT / "ansible/roles/kitty/files/catppuccin-mocha.conf").is_file())

    def test_unity_cli_is_optional_on_every_linux_profile(self):
        for profile in configure.LINUX_PROFILES:
            self.assertIn("unity_cli", {app["key"] for app in configure.visible_apps(profile)})
            self.assertNotIn("unity_cli", configure.default_selection(profile))
            playbook = (ROOT / configure.PLAYBOOKS[profile]).read_text(encoding="utf-8")
            self.assertIn("role: unity_cli", playbook)
        self.assertNotIn("unity_cli", {app["key"] for app in configure.visible_apps("macos")})
        config = configure.build_config("ubuntu", configure.default_selection("ubuntu") | {"unity_cli"})
        self.assertTrue(config["install_unity_cli"])

    def test_no_deprecated_top_level_fact_variables(self):
        # INJECT_FACTS_AS_VARS is deprecated; use ansible_facts['name'] instead.
        import re
        # Connection/behaviour variables are fine; only facts moved under ansible_facts.
        allowed = {"ansible_facts", "ansible_check_mode", "ansible_connection", "ansible_python_interpreter"}
        files = list((ROOT / "ansible").rglob("*.yml")) + [ROOT / "tools/configure.py"]
        for path in files:
            for name in re.findall(r"\bansible_[a-z_]+", path.read_text(encoding="utf-8")):
                self.assertIn(name, allowed, f"{path.relative_to(ROOT)} uses {name}")

    def test_installer_clears_cached_sudo_before_detecting_nopasswd(self):
        text = (ROOT / "install").read_text(encoding="utf-8")
        self.assertLess(text.index("sudo -k"), text.index("if sudo -n true"))
        # sudo-rs prompts aren't recognized by Ansible; the installer switches to sudo.ws.
        self.assertIn("export ANSIBLE_BECOME_EXE=sudo.ws", text)

    def test_desktop_hides_server_defaults_as_optional(self):
        ubuntu_defaults = configure.default_selection("ubuntu")
        server_defaults = configure.default_selection("ubuntu_server")
        self.assertIn("opencode_cli", ubuntu_defaults)
        self.assertIn("tmux", server_defaults)
        self.assertIn("tailscale", server_defaults)
        self.assertNotIn("tmux", ubuntu_defaults)
        fedora_defaults = configure.default_selection("fedora_asahi")
        self.assertIn("opencode_cli", fedora_defaults)

    def test_screenshot_tooling(self):
        ubuntu = (ROOT / "ansible/group_vars/ubuntu.yml").read_text(encoding="utf-8")
        fedora = (ROOT / "ansible/group_vars/fedora_asahi.yml").read_text(encoding="utf-8")
        for tool in ("flameshot", "ksnip", "grim", "slurp", "swappy"):
            self.assertNotIn(f"{tool}", ubuntu)
            self.assertNotIn("flameshot", fedora)
        gnome_role = (ROOT / "ansible/roles/gnome/tasks/main.yml").read_text(encoding="utf-8")
        self.assertIn("show-screenshot-ui", gnome_role)
        self.assertIn("Free the Print key", gnome_role)
        self.assertIn("wayshot_keybinding_path", gnome_role)
        self.assertIn("Bind Print to WayShot", gnome_role)
        self.assertIn("gnome_screenshots_redirect_target", gnome_role)
        self.assertIn("Ensure the screenshots redirect target and its link parent exist", gnome_role)
        ubuntu_playbook = (ROOT / "ansible/playbooks/ubuntu.yml").read_text(encoding="utf-8")
        self.assertIn("flatpaks", ubuntu_playbook)
        self.assertNotIn("ksnip -r", gnome_role)
        fedora_playbook = (ROOT / "ansible/playbooks/fedora_asahi.yml").read_text(encoding="utf-8")
        self.assertIn("role: wayshot", fedora_playbook)
        wayshot_role = (ROOT / "ansible/roles/wayshot/tasks/main.yml").read_text(encoding="utf-8")
        self.assertIn("X-KDE-Shortcuts", wayshot_role)
        self.assertIn("org.kde.spectacle.desktop", wayshot_role)

    def test_wayshot_selection(self):
        selected = configure.default_selection("ubuntu")
        self.assertIn("wayshot", selected)
        config = configure.build_config("ubuntu", selected)
        self.assertTrue(config["install_flatpak_apps"])
        self.assertIn("io.github.gutopardini.wayshot", config["flatpak_packages"])
        server_selected = configure.default_selection("ubuntu_server")
        self.assertNotIn("wayshot", server_selected)

    def test_profile_vars_enable_opencode_cli(self):
        ubuntu = (ROOT / "ansible/group_vars/ubuntu.yml").read_text(encoding="utf-8")
        fedora = (ROOT / "ansible/group_vars/fedora_asahi.yml").read_text(encoding="utf-8")
        server = (ROOT / "ansible/group_vars/ubuntu_server.yml").read_text(encoding="utf-8")
        example = (ROOT / "ansible/group_vars/local.yml.example").read_text(encoding="utf-8")
        self.assertIn("install_opencode_cli: true", ubuntu)
        self.assertIn("install_opencode_cli: true", fedora)
        self.assertIn("install_opencode_cli: true", server)
        self.assertIn("install_opencode_cli: true", example)
        for text in (ubuntu, fedora, server, example):
            self.assertNotIn("install_opencode_desktop", text)

    def test_generated_local_yml_overrides_profile_opencode_cli(self):
        def load(name):
            return parse_yaml((ROOT / "ansible/group_vars" / name).read_text(encoding="utf-8"))

        merged = {}
        merged.update(load("all.yml"))
        merged.update(load("ubuntu.yml"))
        self.assertTrue(merged["install_opencode_cli"])
        merged.update({"install_opencode_cli": False})
        self.assertFalse(merged["install_opencode_cli"])


class TestUfw(unittest.TestCase):
    def test_ssh_is_allowed_by_port_not_app_profile(self):
        role = (ROOT / "ansible/roles/ufw/tasks/main.yml").read_text(encoding="utf-8")
        self.assertIn('- "{{ ufw_ssh_port }}/tcp"', role)
        self.assertIn("ufw_ssh_port ~ '/tcp|OpenSSH'", role)
        self.assertNotIn('- OpenSSH', role)
        all_vars = parse_yaml((ROOT / "ansible/group_vars/all.yml").read_text(encoding="utf-8"))
        self.assertEqual(all_vars["ufw_ssh_port"], 22)


class TestTimeshift(unittest.TestCase):
    def test_initial_snapshot_is_protected_from_idle_and_screen_lock(self):
        role = (ROOT / "ansible/roles/timeshift/tasks/main.yml").read_text(encoding="utf-8")
        self.assertIn("systemd-inhibit", role)
        self.assertIn("--what=idle:sleep:handle-lid-switch", role)
        self.assertIn("kscreenlockerrc", role)
        self.assertIn("suspendType 0", role)
        all_vars = parse_yaml((ROOT / "ansible/group_vars/all.yml").read_text(encoding="utf-8"))
        self.assertEqual(all_vars["kde_screen_lock_timeout"], 1)
        fedora = parse_yaml((ROOT / "ansible/group_vars/fedora_asahi.yml").read_text(encoding="utf-8"))
        self.assertTrue(fedora["kde_disable_autosuspend"])


class TestUbuntuSupport(unittest.TestCase):
    def test_installer_accepts_both_lts_versions(self):
        text = (ROOT / "install").read_text(encoding="utf-8")
        self.assertIn('CHINOOK_UBUNTU_VERSIONS="24.04 26.04"', text)

    def test_readme_documents_wget_and_2604(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("wget -qO- https://github.com/ricardo-alternova/chinook/releases/latest/download/install | bash", text)
        self.assertIn("26.04", text)

    def test_installer_accepts_fedora_asahi_remix_os_id(self):
        text = (ROOT / "install").read_text(encoding="utf-8")
        # OS detection and both package-manager paths (git and the full prerequisite set).
        self.assertEqual(text.count("fedora|fedora-asahi-remix|fedora-asahi)"), 3)

    def test_manual_install_documents_sudo_ws(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        manual = text[text.index("### Manual install"):text.index("## Next steps")]
        self.assertIn("ANSIBLE_BECOME_EXE=sudo.ws", manual)

    def test_local_paths_follow_xdg_user_dirs(self):
        all_vars = parse_yaml((ROOT / "ansible/group_vars/all.yml").read_text(encoding="utf-8"))
        self.assertEqual(all_vars["dev_dir"], "")
        self.assertEqual(all_vars["gnome_screenshots_dir"], "")
        self.assertEqual(all_vars["gnome_screenshots_redirect_target"], "")
        loader = parse_yaml((ROOT / "ansible/playbooks/tasks/load_local_vars.yml").read_text(encoding="utf-8"))
        commands = [task.get("ansible.builtin.command") for task in loader if "ansible.builtin.command" in task]
        self.assertIn("xdg-user-dir {{ item }}", commands)
        defaults = next(task for task in loader if task.get("name") == "Default local paths to the user's XDG directories")
        facts = defaults["ansible.builtin.set_fact"]
        for name in ("dev_dir", "gnome_screenshots_dir", "gnome_screenshots_redirect_target"):
            self.assertIn(name, facts)
            self.assertIn("xdg_", facts[name])

    def test_gnome_only_frees_print_for_wayshot(self):
        tasks = parse_yaml((ROOT / "ansible/roles/gnome/tasks/main.yml").read_text(encoding="utf-8"))
        by_name = {task["name"]: task for task in tasks}
        fact = by_name["Determine whether WayShot will be installed"]["ansible.builtin.set_fact"]["wayshot_selected"]
        self.assertIn("install_flatpak_apps", fact)
        self.assertIn("wayshot_selected", by_name["Free the Print key from the GNOME screenshot UI"]["when"])
        self.assertIn("Restore the GNOME screenshot UI binding when WayShot is not selected", by_name)


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
        self.assertTrue(config["install_opencode_cli"])
        self.assertFalse(config["install_grok_bot"])
        self.assertFalse(config["install_cursor"])
        self.assertTrue(config["install_flatpak_apps"])
        self.assertIn("io.github.gutopardini.wayshot", config["flatpak_packages"])
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


class TestGenerateLocalYml(unittest.TestCase):
    def test_roundtrip_and_mode(self):
        selected = configure.default_selection("ubuntu")
        config = configure.build_config("ubuntu", selected)
        text = configure.generate_local_yml("ubuntu", config)
        data = parse_yaml(text)
        self.assertEqual(data["profile"], "ubuntu")
        # User and home come from the account running the playbook, never local.yml.
        self.assertNotIn("workstation_user", data)
        self.assertNotIn("workstation_home", data)
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
        text = configure.generate_local_yml("ubuntu_server", config)
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


class TestDetection(unittest.TestCase):
    def packages(self, **managers):
        found = {name: set(managers.get(name, [])) for name in ("apt", "dnf", "snap", "flatpak", "brew", "cask")}
        found["system"] = found["apt"] | found["dnf"] | found["brew"] | found["cask"]
        return found

    def app(self, key):
        return next(app for app in configure.APPS if app["key"] == key)

    def test_package_apps_need_every_package(self):
        gimp = self.app("gimp")
        self.assertTrue(configure.app_installed(gimp, "ubuntu", self.packages(apt=["gimp"])))
        self.assertFalse(configure.app_installed(gimp, "ubuntu", self.packages()))
        codecs = self.app("codecs")
        self.assertFalse(configure.app_installed(codecs, "ubuntu", self.packages(apt=["ffmpeg"])))
        self.assertTrue(configure.app_installed(codecs, "ubuntu", self.packages(apt=codecs["apt"])))

    def test_snap_and_flatpak_apps_follow_the_profile(self):
        discord = self.app("discord")
        self.assertTrue(configure.app_installed(discord, "ubuntu", self.packages(snap=["discord"])))
        self.assertFalse(configure.app_installed(discord, "fedora_asahi", self.packages(snap=["discord"])))
        self.assertTrue(configure.app_installed(discord, "fedora_asahi", self.packages(flatpak=["com.discordapp.Discord"])))

    def test_flag_apps_use_their_package_or_path(self):
        self.assertTrue(configure.app_installed(self.app("docker"), "ubuntu", self.packages(apt=["docker-ce"])))
        self.assertTrue(configure.app_installed(self.app("fleet"), "fedora_asahi", self.packages(dnf=["fleet-osquery"])))
        self.assertFalse(configure.app_installed(self.app("compai_agent"), "ubuntu", self.packages()))
        with tempfile.TemporaryDirectory() as home:
            claude = Path(home) / ".local" / "bin" / "claude"
            claude.parent.mkdir(parents=True)
            with patch.dict(os.environ, {"HOME": home}):
                self.assertFalse(configure.app_installed(self.app("claude_code"), "ubuntu", self.packages()))
                claude.touch()
                self.assertTrue(configure.app_installed(self.app("claude_code"), "ubuntu", self.packages()))

    def test_every_app_can_be_detected(self):
        for profile in configure.PLAYBOOKS:
            managers = configure.profile_managers(profile)
            for app in configure.visible_apps(profile):
                if app.get("no_detect"):
                    continue
                installs_something = configure.app_flags(app) or any(app.get(manager) for manager in managers)
                if not installs_something:
                    continue
                detectable = (
                    app.get("detect") or app.get("detect_paths") or app.get("detect_packages")
                    or any(app.get(manager) for manager in managers)
                )
                self.assertTrue(detectable, f"{app['key']} on {profile}")

    def test_previous_local_yml_round_trips(self):
        selected = configure.default_selection("ubuntu") - {"zed"} | {"gimp", "fleet"}
        config = configure.build_config("ubuntu", selected)
        config["fleet_enroll_secret"] = "s3cret+abc"
        data = configure.read_local_yml_text(configure.generate_local_yml("ubuntu", config))
        self.assertEqual(configure.previous_selection("ubuntu", data), selected)
        self.assertEqual(data["fleet_enroll_secret"], "s3cret+abc")


class TestMacosProfile(unittest.TestCase):
    def app(self, key):
        return next(app for app in configure.APPS if app["key"] == key)

    def packages(self, **managers):
        found = {name: set(managers.get(name, [])) for name in ("apt", "dnf", "snap", "flatpak", "brew", "cask")}
        found["system"] = set().union(*found.values())
        return found

    def test_playbook_uses_shared_roles_and_checks_the_os(self):
        self.assertEqual(configure.PLAYBOOKS["macos"], "ansible/playbooks/macos.yml")
        text = (ROOT / "ansible/playbooks/macos.yml").read_text(encoding="utf-8")
        self.assertIn("ansible_facts['system'] != 'Darwin'", text)
        for role in ("hostname", "homebrew", "ssh_client", "opencode_cli", "codex_cli", "claude_code", "cursor_cli", "fleet"):
            self.assertIn(f"role: {role}", text)
        for role in ("packages", "snaps", "flatpaks", "timeshift", "gnome", "kde", "docker", "ufw", "fail2ban", "shell"):
            self.assertNotIn(f"role: {role}", text)

    def test_only_apps_with_a_macos_install_are_offered(self):
        for app in configure.visible_apps("macos"):
            self.assertTrue(
                app.get("brew") or app.get("cask") or configure.app_flags(app),
                app["key"],
            )
        keys = {app["key"] for app in configure.visible_apps("macos")}
        for linux_only in (
            "shell", "tmux", "tailscale", "ufw", "fail2ban", "codecs", "heif", "wayshot",
            "input_remapper", "helium", "unity_hub", "xournalpp", "onedrive", "mangohud",
            "compai_agent", "unity_cli", "grok_bot", "t3_code",
            "steam", "zapzap", "balena_etcher", "teams_pwa", "keychron",
        ):
            self.assertNotIn(linux_only, keys, linux_only)

    def test_defaults_only_tick_fleet(self):
        selected = configure.default_selection("macos")
        self.assertEqual(selected, {"fleet"})
        config = configure.build_config("macos", selected)
        self.assertTrue(config["install_packages"])
        self.assertTrue(config["install_fleet"])
        self.assertFalse(config["install_claude_code"])
        self.assertFalse(config["configure_ssh"])
        for key in ("apt_packages", "dnf_packages", "snap_packages", "flatpak_packages"):
            self.assertNotIn(key, config)
        self.assertEqual(config["brew_packages"], [])
        self.assertEqual(config["brew_casks"], [])

    def test_homebrew_formulae_and_casks(self):
        selected = configure.default_selection("macos") | {"base_cli", "chrome", "zed"}
        config = configure.build_config("macos", selected)
        self.assertEqual(config["brew_packages"], ["git", "jq"])
        self.assertEqual(config["brew_casks"], ["google-chrome", "zed"])

    def test_chrome_label_matches_macos(self):
        chrome = self.app("chrome")
        self.assertEqual(configure.app_label(chrome, "macos"), "Google Chrome")
        self.assertIn("Ubuntu", configure.app_label(chrome, "ubuntu"))

    def test_detection_uses_homebrew_and_applications(self):
        base = self.app("base_cli")
        self.assertTrue(configure.app_installed(base, "macos", self.packages(brew=["git", "jq"])))
        self.assertFalse(configure.app_installed(base, "macos", self.packages(brew=["git"])))
        chrome = self.app("chrome")
        self.assertTrue(configure.app_installed(chrome, "macos", self.packages(cask=["google-chrome"])))
        with patch.object(configure.glob, "glob", return_value=["/Applications/Google Chrome.app"]):
            self.assertTrue(configure.app_installed(chrome, "macos", self.packages()))
            # A Linux profile never installs into /Applications.
            self.assertFalse(configure.app_installed(chrome, "ubuntu", self.packages()))

    def test_previous_selection_round_trips(self):
        selected = configure.default_selection("macos") | {"base_cli", "chrome", "glab", "zed", "cursor"}
        config = configure.build_config("macos", selected)
        data = configure.read_local_yml_text(configure.generate_local_yml("macos", config))
        self.assertEqual(configure.previous_selection("macos", data), selected)

    def test_unmanaged_casks_are_reported_not_installed(self):
        config = configure.build_macos_config({"fleet", "chrome"}, unmanaged_casks={"chrome"})
        self.assertEqual(config["brew_casks"], [])
        self.assertEqual(config["brew_casks_present"], ["google-chrome"])
        data = parse_yaml(configure.generate_local_yml("macos", config))
        self.assertEqual(data["brew_casks"], [])
        self.assertEqual(data["brew_casks_present"], ["google-chrome"])

    def test_detection_separates_homebrew_managed_casks(self):
        chrome_path = "/Applications/Google Chrome.app"

        def detect(casks):
            packages = self.packages(cask=casks)
            with patch.object(configure.sys, "platform", "darwin"), \
                 patch.object(configure, "installed_packages", return_value=packages), \
                 patch.object(configure.glob, "glob", side_effect=lambda path: [chrome_path] if path == chrome_path else []):
                return configure.detect_installation("macos")

        installed, unmanaged = detect([])
        self.assertIn("chrome", installed)
        self.assertEqual(unmanaged, {"chrome"})
        installed, unmanaged = detect(["google-chrome"])
        self.assertIn("chrome", installed)
        self.assertNotIn("chrome", unmanaged)

    def test_fleet_role_builds_and_loads_a_pkg(self):
        enroll = (ROOT / "ansible/roles/fleet/tasks/enroll.yml").read_text(encoding="utf-8")
        self.assertIn("'pkg'", enroll)
        self.assertIn("installer", enroll)
        self.assertIn("launchctl", enroll)
        self.assertIn("fleetctl_archive_ext", enroll)
        self.assertIn("fleet_macos_plist", enroll)
        # fleetctl only accepts --end-user-email on Windows and Linux.
        self.assertIn("and not fleet_macos", enroll)

    def test_homebrew_role_installs_formulae_and_casks(self):
        role = (ROOT / "ansible/roles/homebrew/tasks/main.yml").read_text(encoding="utf-8")
        self.assertIn("brew_packages", role)
        self.assertIn("brew_casks", role)
        self.assertIn("--cask", role)
        self.assertIn("/opt/homebrew/bin/brew", role)
        self.assertIn("shellenv", role)


class TestTuiProcess(unittest.TestCase):
    def run_tui(self, args, answers, timeout=8, existing=None):
        result, output, tmp = run_tui(args, answers, timeout, existing)
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
            ["", ""],
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertTrue(output.exists())
        data = parse_yaml(output.read_text(encoding="utf-8"))
        self.assertEqual(data["profile"], "ubuntu")
        self.assertNotIn("workstation_user", data)
        self.assertNotIn("workstation_hostname", data)
        self.assertNotIn("fleet_enroll_secret", data)
        self.assertFalse(data["install_fleet"])
        self.assertFalse(data["install_compai_agent"])
        self.assertTrue(data["configure_gnome"])
        self.assertTrue(data["install_opencode_cli"])
        self.assertIn("Wrote", result.stdout)
        self.assertIn("ansible/playbooks/ubuntu.yml", result.stdout)

    def test_ubuntu_without_preset_profile_choice(self):
        result, output = self.run_tui(
            [],
            ["1", "", ""],
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        data = parse_yaml(output.read_text(encoding="utf-8"))
        self.assertEqual(data["profile"], "ubuntu")

    def test_ubuntu_server_extra_prompts(self):
        result, output = self.run_tui(
            ["--profile", "ubuntu_server"],
            [
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

    def test_macos_defaults_tick_fleet_only(self):
        result, output = self.run_tui(
            ["--profile", "macos"],
            ["", "", "john-doe", ""],
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        data = parse_yaml(output.read_text(encoding="utf-8"))
        self.assertEqual(data["profile"], "macos")
        self.assertTrue(data["install_fleet"])
        self.assertTrue(data["install_packages"])
        self.assertFalse(data["install_claude_code"])
        self.assertEqual(data["workstation_hostname"], "john-doe")
        # fleetd learns the owner's email through MDM enrollment on macOS.
        self.assertNotIn("fleet_end_user_email", data)
        self.assertEqual(data["brew_packages"], [])
        self.assertEqual(data["brew_casks"], [])
        for key in ("apt_packages", "dnf_packages", "snap_packages", "flatpak_packages"):
            self.assertNotIn(key, data)
        self.assertIn("ansible/playbooks/macos.yml", result.stdout)

    def test_macos_tui_writes_homebrew_lists(self):
        picks = f"{app_index('macos', 'base_cli')} {app_index('macos', 'chrome')}"
        result, output = self.run_tui(
            ["--profile", "macos"],
            [picks, "", "", "john-doe", ""],
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        data = parse_yaml(output.read_text(encoding="utf-8"))
        self.assertEqual(data["brew_packages"], ["git", "jq"])
        self.assertEqual(data["brew_casks"], ["google-chrome"])
        self.assertTrue(data["install_fleet"])

    def test_fedora_removals_keep_one(self):
        result, output = self.run_tui(
            ["--profile", "fedora_asahi"],
            ["", "", "1", ""],
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
        fleet = app_index("ubuntu", "fleet")
        result, output = self.run_tui(
            ["--profile", "ubuntu"],
            [
                onedrive,
                fleet,
                "",
                "y",
                "gitlab.com",
                "",
                "~/.ssh/id_ed25519_gitlab",
                "Not Valid!",
                "John-Doe",
                "s3cret+abc",
                "john@example.com",
                "~/OneDrive/Work",
                "Documents, Photos",
            ],
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        data = parse_yaml(output.read_text(encoding="utf-8"))
        self.assertTrue(data["install_onedrive"])
        self.assertTrue(data["install_fleet"])
        self.assertTrue(data["configure_ssh"])
        self.assertEqual(data["ssh_hosts"][0]["host"], "gitlab.com")
        self.assertEqual(data["ssh_hosts"][0]["hostname"], "gitlab.com")
        self.assertEqual(data["onedrive_sync_dir"], "~/OneDrive/Work")
        self.assertEqual(data["onedrive_sync_list"], ["Documents", "Photos"])
        self.assertEqual(data["workstation_hostname"], "john-doe")
        self.assertEqual(data["fleet_enroll_secret"], "s3cret+abc")
        self.assertEqual(data["fleet_end_user_email"], "john@example.com")


    def test_rerun_keeps_previous_answers(self):
        selected = configure.default_selection("ubuntu") - {"zed"} | {"fleet"}
        config = configure.build_config("ubuntu", selected)
        config["fleet_enroll_secret"] = "s3cret+abc"
        config["fleet_end_user_email"] = "john@example.com"
        result, output = self.run_tui(
            ["--profile", "ubuntu"],
            ["", "", "john-doe", "", "", ""],
            existing=configure.generate_local_yml("ubuntu", config),
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        data = parse_yaml(output.read_text(encoding="utf-8"))
        self.assertFalse(data["install_zed"])
        self.assertTrue(data["install_fleet"])
        self.assertEqual(data["fleet_enroll_secret"], "s3cret+abc")
        self.assertEqual(data["fleet_end_user_email"], "john@example.com")
        self.assertNotIn("s3cret", result.stdout)


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
        # Backticks in an unquoted heredoc would run `opencode auth login` and hang.
        self.assertIn("cat <<'EOF'\n\nChinook is ready.", text)
        self.assertNotIn("cat <<EOF", text)

    def test_ubuntu_profile_override_rejects_fedora(self):
        text = (ROOT / "install").read_text(encoding="utf-8")
        self.assertIn("On Ubuntu, CHINOOK_PROFILE must be ubuntu or ubuntu_server", text)

    def test_macos_bootstrap(self):
        text = (ROOT / "install").read_text(encoding="utf-8")
        self.assertIn("is_macos()", text)
        self.assertIn("ensure_homebrew", text)
        self.assertIn("brew install ansible", text)
        self.assertIn("ansible/playbooks/macos.yml", text)
        self.assertIn("curl -fsSL", text)
        # macOS has no /etc/os-release, so detection must branch before reading it.
        detect = text[text.index("detect_os()"):text.index("choose_ubuntu_profile()")]
        self.assertLess(detect.index("is_macos"), detect.index("/etc/os-release"))
        # bash 3.2 treats an empty array as unset under set -u.
        self.assertIn('${become[@]+"${become[@]}"}', text)


if __name__ == "__main__":
    unittest.main()
