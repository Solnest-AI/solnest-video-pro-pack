"""scripts/update.py: installs only a published release into the pack folder, keeps bin/,
keys, editor rules and every file the member added, and --undo puts the old version back.
Offline: releases are read from a local folder (VIDEO_PRO_PACK_RELEASE_DIR)."""
import io
import os
import pathlib
import sys
import tarfile
import tempfile
import unittest
from unittest import mock

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import update  # noqa: E402

FAKE_ENV = "SOME_KEY=fake_test_" + "0" * 24 + "\n"   # made up, never a real key
KIT_JSON = '{"kit": "video-pro-pack"}\n'
RUNBOOK = "old runbook\n## SETUP\n"


def tarball(folder, version, files, top=None):
    """A GitHub-style source tarball: one top folder, the pack at its root."""
    top = top or f"solnest-video-pro-pack-{version}"
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        def add(rel, data):
            info = tarfile.TarInfo(f"{top}/{rel}")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        add("VERSION", f"{version}\n".encode())
        for rel, text in files.items():
            add(rel, text.encode())
    (pathlib.Path(folder) / f"v{version}.tar.gz").write_bytes(buf.getvalue())


class UpdateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = pathlib.Path(self.tmp.name)
        self.rel = base / "releases"
        self.rel.mkdir()
        self.root = base / "solnest" / "video-pro-pack"
        self.root.mkdir(parents=True)
        env = mock.patch.dict(os.environ, {update.LOCAL_RELEASES: str(self.rel)})
        env.start()
        self.addCleanup(env.stop)
        self.addCleanup(self.tmp.cleanup)
        old = {"kit.json": KIT_JSON, "CLAUDE.md": RUNBOOK, "README.md": "old readme\n",
               "scripts/update.py": "x = 1\n", "scripts/dropped.py": "# gone next\n",
               "skills/heygen-video/SKILL.md": "video v1\n",
               "skills/heygen-video/references/old-page.md": "dropped next\n",
               "skills/vox-explainer/SKILL.md": "vox v1\n"}
        tarball(self.rel, "1.0.0", old)
        for rel, text in old.items():
            (self.root / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.root / rel).write_text(text, encoding="utf-8")
        (self.root / "VERSION").write_text("1.0.0\n", encoding="utf-8")
        # the member's own things
        self.mine = {
            ".env": FAKE_ENV.encode(),
            "bin/py": b"fake launcher\n",
            ".cursor/rules/private.mdc": b"private rules\n",
            "my-notes.md": b"mine\n",
            "scripts/my-helper.sh": b"mine too\n",
            "skills/heygen-video/my-brand-notes.md": b"my brand\n",
            "skills/vox-explainer/scripts/node_modules/x/index.js": b"installed by the skill's own setup\n",
            "skills/my-own-skill/SKILL.md": b"a skill I wrote\n",
        }
        for rel, data in self.mine.items():
            (self.root / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.root / rel).write_bytes(data)

    def _new_release(self):
        tarball(self.rel, "1.1.0", {"kit.json": KIT_JSON, "CLAUDE.md": RUNBOOK.replace("old", "new"),
                                    "README.md": "new readme\n", "scripts/update.py": "x = 2\n",
                                    "scripts/new.py": "# brand new\n",
                                    "skills/heygen-video/SKILL.md": "video v2\n",
                                    "skills/vox-explainer/SKILL.md": "vox v2\n",
                                    "skills/new-skill/SKILL.md": "new in v2\n",
                                    "bin/py": "release must not win\n", ".env": "EVIL=from_release\n",
                                    ".cursor/rules/private.mdc": "release must not win\n",
                                    "skills/vox-explainer/scripts/node_modules/x/index.js": "evil\n"})

    def _member_files_intact(self):
        for rel, data in self.mine.items():
            self.assertEqual((self.root / rel).read_bytes(), data, rel)

    def test_update_keeps_member_files_and_undo_goes_back(self):
        self._new_release()
        r = update.update(self.root)
        self.assertEqual(r["status"], "updated")
        self.assertEqual((self.root / "VERSION").read_text().strip(), "1.1.0")
        self.assertIn("new runbook", (self.root / "CLAUDE.md").read_text())
        self.assertEqual((self.root / "skills/heygen-video/SKILL.md").read_text(), "video v2\n")
        self.assertEqual((self.root / "skills/new-skill/SKILL.md").read_text(), "new in v2\n")
        self.assertTrue((self.root / "scripts" / "new.py").is_file())
        self.assertFalse((self.root / "scripts" / "dropped.py").exists())   # shipped by 1.0.0, not 1.1.0
        self.assertFalse((self.root / "skills/heygen-video/references").exists())
        self._member_files_intact()
        self.assertEqual(update.update(self.root)["status"], "current")

        update.undo(self.root)
        self.assertEqual((self.root / "VERSION").read_text().strip(), "1.0.0")
        self.assertIn("old runbook", (self.root / "CLAUDE.md").read_text())
        self.assertEqual((self.root / "skills/heygen-video/SKILL.md").read_text(), "video v1\n")
        self.assertEqual((self.root / "skills/heygen-video/references/old-page.md").read_text(), "dropped next\n")
        self.assertTrue((self.root / "scripts" / "dropped.py").is_file())
        self.assertFalse((self.root / "scripts" / "new.py").exists())
        self.assertFalse((self.root / "skills/new-skill").exists())
        self.assertFalse((self.root / update.BACKUP_DIR).exists())
        self._member_files_intact()

    def test_manifest_lists_what_shipped_and_removal_follows_it(self):
        self._new_release()
        update.update(self.root)
        self.assertEqual(set(update.load_manifest(self.root)),
                         {"VERSION", "kit.json", "CLAUDE.md", "README.md", "scripts/update.py", "scripts/new.py",
                          "skills/heygen-video/SKILL.md", "skills/vox-explainer/SKILL.md",
                          "skills/new-skill/SKILL.md"})
        # the next release drops a skill and a script: the manifest is what gets them removed
        tarball(self.rel, "1.2.0", {"kit.json": KIT_JSON, "CLAUDE.md": RUNBOOK, "README.md": "newer\n",
                                    "scripts/update.py": "x = 3\n", "skills/heygen-video/SKILL.md": "video v3\n",
                                    "skills/vox-explainer/SKILL.md": "vox v3\n"})
        r = update.update(self.root)
        self.assertEqual(r["removed"], ["scripts/new.py", "skills/new-skill/SKILL.md"])
        self.assertFalse((self.root / "skills/new-skill").exists())
        self._member_files_intact()

    def test_without_a_manifest_the_old_release_says_what_to_remove(self):
        """A copy straight from the installer on an older machine may have no manifest."""
        self.assertFalse((self.root / update.MANIFEST).exists())
        self._new_release()
        r = update.update(self.root)
        self.assertIn("scripts/dropped.py", r["removed"])
        self._member_files_intact()

    def test_without_a_manifest_or_the_old_release_nothing_is_removed(self):
        (self.rel / "v1.0.0.tar.gz").unlink()
        self._new_release()
        r = update.update(self.root)
        self.assertEqual(r["removed"], [])
        self.assertTrue((self.root / "scripts" / "dropped.py").is_file())
        self.assertEqual((self.root / "VERSION").read_text().strip(), "1.1.0")
        self._member_files_intact()

    def test_stamp_records_the_pack_files_only(self):
        """install.sh's last step."""
        src = pathlib.Path(self.tmp.name) / "fresh"
        files = {"VERSION": "1.0.0\n", "kit.json": KIT_JSON, "skills/duo-like/SKILL.md": "x\n",
                 ".env": "nope\n", "bin/py": "nope\n", ".cursor/rules/a.mdc": "nope\n"}
        for rel, text in files.items():
            (src / rel).parent.mkdir(parents=True, exist_ok=True)
            (src / rel).write_text(text, encoding="utf-8")
        self.assertEqual(update.stamp(src, self.root), 3)
        self.assertEqual(set(update.load_manifest(self.root)), {"VERSION", "kit.json", "skills/duo-like/SKILL.md"})

    def test_edited_pack_file_is_reported_and_saved(self):
        (self.root / "skills/heygen-video/SKILL.md").write_text("the member edited this\n", encoding="utf-8")
        self._new_release()
        r = update.update(self.root)
        self.assertIn("skills/heygen-video/SKILL.md", r["edited"])
        self.assertEqual((pathlib.Path(r["backup"]) / "skills/heygen-video/SKILL.md").read_text(),
                         "the member edited this\n")

    def test_protected_paths(self):
        want = {".env": True, "sub/.env": True, ".env.local": True, ".env.example": False, "keys.env": True,
                ".cache/x": True, "bin/py": True, "bin/py.cmd": True, "tokens.json": True, "a.token": True,
                ".cursor/rules/x.mdc": True, "skills/heygen-video/.cursor/rules/x.mdc": True,
                "skills/session-story/scripts/node_modules/p5/p5.js": True,
                ".venv/lib/x.py": True, ".update-backup/1/undo.json": True, update.MANIFEST: True,
                "skills/heygen-video/SKILL.md": False, "skills/session-story/scripts/setup.sh": False,
                "skills/session-story/scripts/package-lock.json": False, "scripts/own-changes-block.md": False,
                "kit.json": False, "CLAUDE.md": False, "README.md": False, "install.sh": False,
                "THIRD_PARTY_NOTICES.md": False, "scripts/setup.py": False, "scripts/update.py": False,
                "scripts/solnest_autoupdate.py": False}
        for rel, protected in want.items():
            self.assertEqual(update._protected(rel), protected, rel)

    def test_every_file_this_repo_ships_can_be_updated(self):
        """A shipped path that reads as protected would never reach a member."""
        skip = {".git", ".cursor", ".pytest_cache", "__pycache__", "bin", ".update-backup", "node_modules"}
        for path in sorted(REPO.rglob("*")):
            rel = path.relative_to(REPO)
            if path.is_file() and not set(rel.parts) & skip and path.name not in (".DS_Store", update.MANIFEST):
                self.assertFalse(update._protected(rel.as_posix()), rel.as_posix())

    def test_refuses_a_git_checkout(self):
        (self.root / ".git").mkdir()
        self._new_release()
        with self.assertRaises(update.UpdateError):
            update.update(self.root)
        self.assertEqual((self.root / "VERSION").read_text().strip(), "1.0.0")

    def test_unsafe_release_changes_nothing(self):
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            for name in ("top/VERSION", "../evil"):
                info = tarfile.TarInfo(name)
                info.size = 1
                tar.addfile(info, io.BytesIO(b"x"))
        (self.rel / "v1.1.0.tar.gz").write_bytes(buf.getvalue())
        with self.assertRaises(update.UpdateError):
            update.update(self.root)
        self.assertEqual((self.root / "VERSION").read_text().strip(), "1.0.0")
        self.assertIn("old runbook", (self.root / "CLAUDE.md").read_text())

    def test_mislabelled_release_is_refused(self):
        tarball(self.rel, "1.1.0", {"kit.json": KIT_JSON})
        blob = (self.rel / "v1.1.0.tar.gz").read_bytes()
        (self.rel / "v1.1.0.tar.gz").unlink()
        (self.rel / "v1.3.0.tar.gz").write_bytes(blob)     # tag says 1.3.0, VERSION inside says 1.1.0
        with self.assertRaises(update.UpdateError):
            update.update(self.root)
        self.assertEqual((self.root / "VERSION").read_text().strip(), "1.0.0")

    def test_a_release_of_something_else_is_refused(self):
        tarball(self.rel, "1.1.0", {"CLAUDE.md": "no kit.json here\n"})
        with self.assertRaises(update.UpdateError):
            update.update(self.root)
        self.assertEqual((self.root / "VERSION").read_text().strip(), "1.0.0")

    def test_no_release_yet_is_a_plain_error(self):
        for p in self.rel.glob("*"):
            p.unlink()
        with self.assertRaises(update.UpdateError):
            update.update(self.root)


if __name__ == "__main__":
    unittest.main()
