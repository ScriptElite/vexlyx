"""The repository URL the installer clones from by default.

`install.sh` and `system/scripts/install/config.sh` each carry their own copy of the
default, and the landing page's DEPLOY.md tells whoever publishes the installer to
check that both still match — a fresh install clones with one file's value and the
run.sh orchestrator later fetches with the other's, so a divergence means an upgrade
pulls from a different remote than the install used. The value itself used to name
`atlantiqs-org`, the org slug from before the rename: it worked only because GitHub
redirects a renamed owner (`301 -> https://github.com/atlantiqshq/vexlyx`), so every
new install depended on that redirect continuing to resolve, and on nobody ever
being handed the old slug. It now names the current slug outright.

If the org is renamed again, update both files and this test together.
"""

import re
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
INSTALL_SH = ROOT_DIR / "install.sh"
CONFIG_SH = ROOT_DIR / "system" / "scripts" / "install" / "config.sh"

EXPECTED_REPO_URL = "https://github.com/atlantiqshq/vexlyx.git"
DEFAULT_URL_RE = re.compile(r'VEXLYX_REPO_URL="\$\{VEXLYX_REPO_URL:-([^"}]+)\}"')


def default_repo_url(path: Path) -> str:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    matches = DEFAULT_URL_RE.findall(text)
    if len(matches) != 1:
        raise AssertionError(
            f"expected exactly one VEXLYX_REPO_URL default in {path.name}, found {matches}"
        )
    return matches[0]


class InstallerRepoUrlTest(unittest.TestCase):
    def test_install_sh_and_config_sh_default_to_the_same_url(self) -> None:
        self.assertEqual(
            default_repo_url(INSTALL_SH),
            default_repo_url(CONFIG_SH),
            "the bootstrap clone and the orchestrator must name the same remote",
        )

    def test_the_default_names_the_current_org_slug_not_the_pre_rename_one(self) -> None:
        for path in (INSTALL_SH, CONFIG_SH):
            self.assertEqual(default_repo_url(path), EXPECTED_REPO_URL, path.name)

    def test_the_override_still_wins_over_the_default(self) -> None:
        # The default must stay an ${VAR:-default} expansion: a forked or mirrored
        # install sets VEXLYX_REPO_URL before running the installer, and an
        # unconditional assignment would silently clone from upstream instead.
        for path in (INSTALL_SH, CONFIG_SH):
            self.assertIn("${VEXLYX_REPO_URL:-", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
