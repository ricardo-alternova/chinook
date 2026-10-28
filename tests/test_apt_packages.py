#!/usr/bin/env python3
"""Check that every APT package Chinook installs exists on the supported Ubuntu releases.

Downloads the official Ubuntu package indexes, so it only runs when
CHINOOK_CHECK_APT=1 is set (CI sets it).
"""
import gzip
import importlib.util
import os
import unittest
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIGURE_PATH = ROOT / "tools" / "configure.py"

spec = importlib.util.spec_from_file_location("chinook_configure", CONFIGURE_PATH)
configure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(configure)

try:
    import yaml
except ImportError:
    yaml = None


# Release codenames the Ubuntu profiles support. Add a codename here when a new
# release is supported, and every package name is checked against it too.
UBUNTU_RELEASES = ["noble", "resolute"]  # 24.04 and 26.04 LTS
UBUNTU_COMPONENTS = ["main", "restricted", "universe", "multiverse"]
UBUNTU_ARCHIVE = "http://archive.ubuntu.com/ubuntu"

# Packages that come from third-party APT repositories the roles add themselves.
THIRD_PARTY_PACKAGES = {"google-chrome-stable"}


def release_packages(codename):
    names = set()
    for suite in (codename, f"{codename}-updates"):
        for component in UBUNTU_COMPONENTS:
            url = f"{UBUNTU_ARCHIVE}/dists/{suite}/{component}/binary-amd64/Packages.gz"
            with urllib.request.urlopen(url, timeout=120) as response:
                text = gzip.decompress(response.read()).decode("utf-8", "replace")
            names.update(line[len("Package: "):].strip() for line in text.splitlines() if line.startswith("Package: "))
    return names


def chinook_apt_packages():
    names = set()
    for app in configure.APPS:
        names.update(app.get("apt", []))
    for profile in configure.APT_PROFILES:
        profile_vars = yaml.safe_load((ROOT / "ansible/group_vars" / f"{profile}.yml").read_text(encoding="utf-8"))
        names.update(profile_vars.get("apt_packages", []))
    all_vars = yaml.safe_load((ROOT / "ansible/group_vars/all.yml").read_text(encoding="utf-8"))
    names.update(all_vars.get("fail2ban_packages", []))
    return names - THIRD_PARTY_PACKAGES


class TestSupportedReleases(unittest.TestCase):
    def test_ubuntu_lts_releases_are_listed(self):
        self.assertIn("noble", UBUNTU_RELEASES)
        self.assertIn("resolute", UBUNTU_RELEASES)


@unittest.skipUnless(os.environ.get("CHINOOK_CHECK_APT") == "1", "set CHINOOK_CHECK_APT=1 to download Ubuntu package indexes")
class TestAptPackagesExist(unittest.TestCase):
    def test_packages_exist_on_supported_releases(self):
        if yaml is None:
            self.fail("PyYAML is required: python3 -m pip install pyyaml")
        wanted = chinook_apt_packages()
        self.assertTrue(wanted)
        for codename in UBUNTU_RELEASES:
            with self.subTest(release=codename):
                missing = sorted(wanted - release_packages(codename))
                self.assertEqual(missing, [], f"APT packages missing on Ubuntu {codename}: {', '.join(missing)}")


if __name__ == "__main__":
    unittest.main()
