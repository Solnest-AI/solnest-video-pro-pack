"""install.sh: puts the pack in <home>/solnest/video-pro-pack without the git link, keys or
editor rules, writes the launcher and the file list, keeps the member's files on a second
run, and refuses to overwrite something that is not this pack. Offline: it installs from
this copy of the repo, or from a local archive. It never touches ~/.claude (setup.py does)."""
import os
import pathlib
import shutil
import subprocess
import tarfile
import tempfile
import unittest

REPO = pathlib.Path(__file__).resolve().parent.parent
BASH = shutil.which("bash")
SKIP = {".git", ".cache", "node_modules", "bin", ".update-backup", ".pytest_cache", "__pycache__", ".env",
        ".cursor"}


@unittest.skipUnless(BASH, "needs bash")
class InstallTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = pathlib.Path(self.tmp.name) / "home"
        self.home.mkdir()
        self.dest = self.home / "solnest" / "video-pro-pack"

    def run_install(self, script=None, stdin=None, **extra):
        env = dict(os.environ, HOME=str(self.home), **extra)
        args = [BASH, str(script)] if script else [BASH]
        return subprocess.run(args, env=env, capture_output=True, text=True, timeout=300,
                              stdin=stdin or subprocess.DEVNULL, cwd=self.tmp.name)

    def clone(self):
        src = pathlib.Path(self.tmp.name) / "clone"
        shutil.copytree(REPO, src, ignore=lambda d, names: [n for n in names if n in SKIP])
        return src

    def test_installs_and_a_second_run_keeps_member_files(self):
        r = self.run_install(self.clone() / "install.sh")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("[ok] files", r.stdout)
        self.assertIn("[ok] record", r.stdout)
        for rel in ("kit.json", "VERSION", "CLAUDE.md", "README.md", "THIRD_PARTY_NOTICES.md", "bin/py",
                    "install.sh", "scripts/update.py", "scripts/setup.py", "scripts/solnest_autoupdate.py",
                    "scripts/own-changes-block.md", "skills/heygen-video/SKILL.md", "skills/heygen-video/LICENSE",
                    "skills/session-story/assets/engine/LICENSE-ClaudeAnimationBase",
                    ".video-pro-pack-files.txt"):
            self.assertTrue((self.dest / rel).is_file(), rel)
        self.assertFalse((self.home / ".claude").exists())    # the installer never touches ~/.claude
        self.assertFalse((self.dest / ".git").exists())       # the updater refuses a git checkout
        self.assertEqual((self.dest / "VERSION").read_text(), (REPO / "VERSION").read_text())
        mine = {"my-notes.md": b"mine\n", "skills/heygen-video/my-brand-notes.md": b"my brand\n",
                "skills/session-story/scripts/node_modules/p5/p5.js": b"installed by the skill\n"}
        for rel, data in mine.items():
            (self.dest / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.dest / rel).write_bytes(data)
        (self.dest / "kit.json").unlink()                     # a damaged copy: the repair puts it back
        (self.dest / "skills" / "heygen-video" / "SKILL.md").unlink()
        r = self.run_install(pathlib.Path(self.tmp.name) / "clone" / "install.sh")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for rel, data in mine.items():
            self.assertEqual((self.dest / rel).read_bytes(), data, rel)
        self.assertEqual((self.dest / "kit.json").read_bytes(), (REPO / "kit.json").read_bytes())
        self.assertTrue((self.dest / "skills" / "heygen-video" / "SKILL.md").is_file())

        # repair from inside the installed copy: nothing is copied over itself
        r = self.run_install(self.dest / "install.sh")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("already here", r.stdout)
        self.assertEqual((self.dest / "my-notes.md").read_text(), "mine\n")

    def test_a_source_copy_never_leaks_its_own_state_into_the_install(self):
        src = self.clone()
        (src / ".env").write_text("SOME_KEY=someone_elses_fake\n", encoding="utf-8")
        (src / ".git").mkdir()
        (src / ".cache").mkdir()
        (src / ".cache" / "x").write_text("x\n", encoding="utf-8")
        for folder in (src / ".cursor" / "rules", src / "skills" / "heygen-video" / ".cursor" / "rules"):
            folder.mkdir(parents=True)                        # a sync job drops private rules everywhere
            (folder / "private.mdc").write_text("private rules\n", encoding="utf-8")
        r = self.run_install(src / "install.sh")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue((self.dest / "kit.json").is_file())
        for rel in (".env", ".git", ".cache", ".cursor", "skills/heygen-video/.cursor"):
            self.assertFalse((self.dest / rel).exists(), rel)
        self.assertNotIn(".cursor", (self.dest / ".video-pro-pack-files.txt").read_text())

    def test_piped_install_from_an_archive(self):
        """The `curl ... | bash` path: no local repo, the pack comes from an archive."""
        archive = pathlib.Path(self.tmp.name) / "main.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(REPO, "solnest-video-pro-pack-main",
                    filter=lambda t: None if set(pathlib.PurePosixPath(t.name).parts) & SKIP else t)
        with open(REPO / "install.sh", "rb") as script:
            r = self.run_install(stdin=script, VIDEO_PRO_PACK_ARCHIVE_URL=archive.as_uri())
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("downloading the kit", r.stdout)
        self.assertTrue((self.dest / "kit.json").is_file())
        self.assertTrue((self.dest / "bin" / "py").is_file())
        self.assertTrue((self.dest / "skills" / "vox-explainer" / "SKILL.md").is_file())
        self.assertEqual((self.dest / "VERSION").read_text(), (REPO / "VERSION").read_text())

    def test_refuses_a_different_kit_and_a_git_checkout(self):
        self.dest.mkdir(parents=True)
        (self.dest / "kit.json").write_text('{"kit": "something-else"}\n', encoding="utf-8")
        r = self.run_install(self.clone() / "install.sh")
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertEqual((self.dest / "kit.json").read_text(), '{"kit": "something-else"}\n')
        self.assertFalse((self.dest / "scripts").exists())
        (self.dest / "kit.json").unlink()
        (self.dest / ".git").mkdir()
        r = self.run_install(pathlib.Path(self.tmp.name) / "clone" / "install.sh")
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertFalse((self.dest / "scripts").exists())


if __name__ == "__main__":
    unittest.main()
