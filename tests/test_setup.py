"""scripts/setup.py: copies the pack's skills into <home>/.claude/skills, leaves other
people's copies and the member's own files alone, removes what an earlier copy of the pack
put there and no longer ships, and fetches the two extras from a local folder
(VIDEO_PRO_PACK_EXTRAS_DIR). Offline. Nothing here touches the real home folder."""
import json
import os
import pathlib
import shutil
import sys
import tempfile
import unittest
from unittest import mock

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import setup  # noqa: E402

SEEDANCE = ("---\nname: seedance-cinematic\ndescription: Make film prompts. Triggers on: cinematic, noir. "
            "Use it even without the word \"cinematic\".\n---\n\n# Seedance\n\nBody.\n")
DUO = "---\nname: duo\ndescription: >\n  Two screens on a foldable phone.\n---\n\n# Duo\n\nBody.\n"


class SetupTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = pathlib.Path(self.tmp.name)
        self.home = base / "home"
        self.skills = self.home / ".claude" / "skills"
        self.root = base / "pack"
        for rel, text in {
            "kit.json": json.dumps({"kit": "video-pro-pack", "skills": ["alpha", "beta"]}),
            "VERSION": "1.0.0\n", "CLAUDE.md": "x\n## SETUP\n",
            "scripts/own-changes-block.md": "## Your own changes (read first, every time)\n\nRead the file.\n",
            "scripts/ok.py": "x = 1\n",
            "skills/alpha/SKILL.md": "---\nname: alpha\ndescription: a\n---\n\nalpha v1\n",
            "skills/alpha/references/page.md": "page v1\n",
            "skills/alpha/scripts/run.sh": "echo hi\n",
            "skills/alpha/.cursor/rules/private.mdc": "private rules\n",
            "skills/alpha/.env": "SOME_KEY=fake\n",
            "skills/beta/SKILL.md": "---\nname: beta\ndescription: b\n---\n\nbeta v1\n",
        }.items():
            (self.root / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.root / rel).write_text(text, encoding="utf-8")
        self.extras = base / "extras"
        duo = self.extras / "heygen-com__hyperframes-community-skills"
        for rel in setup._DUO:
            (duo / "skills" / "duo" / rel).parent.mkdir(parents=True, exist_ok=True)
            (duo / "skills" / "duo" / rel).write_bytes(DUO.encode() if rel == "SKILL.md" else b"\x89fake " + rel.encode())
        (duo / "LICENSE").write_text("Apache License\n", encoding="utf-8")
        seed = self.extras / "beshuaxian__higgsfield-seedance2-jineng" / "skills" / "01-cinematic"
        seed.mkdir(parents=True)
        (seed / "SKILL.md").write_text(SEEDANCE, encoding="utf-8")
        env = mock.patch.dict(os.environ, {setup.LOCAL_EXTRAS: str(self.extras)})
        env.start()
        self.addCleanup(env.stop)

    def test_copies_skills_and_keeps_what_is_not_the_packs(self):
        r = setup.install_skills(self.root, self.home)
        self.assertEqual([(t, n) for t, n, _ in r], [("ok", "alpha"), ("ok", "beta")])
        self.assertIn("alpha v1", (self.skills / "alpha" / "SKILL.md").read_text())
        self.assertTrue((self.skills / "alpha" / "references" / "page.md").is_file())
        self.assertTrue(os.access(self.skills / "alpha" / "scripts" / "run.sh", os.X_OK))
        self.assertFalse((self.skills / "alpha" / ".cursor").exists())      # private rules never travel
        self.assertFalse((self.skills / "alpha" / ".env").exists())
        mine = {"alpha/my-notes.md": b"mine\n", "alpha/scripts/node_modules/p5/p5.js": b"installed by the skill\n",
                "alpha/AVATAR-ME.md": b"my avatar\n"}
        for rel, data in mine.items():
            (self.skills / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.skills / rel).write_bytes(data)
        # a newer pack: one page dropped, one added, SKILL.md changed
        (self.root / "skills/alpha/references/page.md").unlink()
        (self.root / "skills/alpha/references/new.md").write_text("new\n", encoding="utf-8")
        (self.root / "skills/alpha/SKILL.md").write_text("---\nname: alpha\ndescription: a\n---\n\nalpha v2\n")
        setup.install_skills(self.root, self.home)
        self.assertIn("alpha v2", (self.skills / "alpha" / "SKILL.md").read_text())
        self.assertFalse((self.skills / "alpha" / "references" / "page.md").exists())
        self.assertTrue((self.skills / "alpha" / "references" / "new.md").is_file())
        for rel, data in mine.items():
            self.assertEqual((self.skills / rel).read_bytes(), data, rel)

    def test_leaves_other_peoples_copies_alone(self):
        (self.skills / "alpha").mkdir(parents=True)
        (self.skills / "alpha" / "SKILL.md").write_text("---\nname: something-else\n---\nnot ours\n")
        target = pathlib.Path(self.tmp.name) / "elsewhere"
        target.mkdir()
        (target / "SKILL.md").write_text("---\nname: beta\n---\nlinked copy\n")
        try:
            (self.skills / "beta").symlink_to(target, target_is_directory=True)
        except OSError:
            self.skipTest("no symlinks here")
        r = setup.install_skills(self.root, self.home)
        self.assertEqual([t for t, _, _ in r], ["--", "--"])
        self.assertIn("not ours", (self.skills / "alpha" / "SKILL.md").read_text())
        self.assertIn("linked copy", (target / "SKILL.md").read_text())
        shutil.rmtree(self.skills / "alpha")
        (self.skills / "alpha" / ".git").mkdir(parents=True)
        self.assertEqual(setup.install_skills(self.root, self.home)[0][0], "--")
        self.assertFalse((self.skills / "alpha" / "SKILL.md").exists())

    def test_same_skill_from_a_plain_copy_is_taken_over_without_removing_anything(self):
        (self.skills / "alpha").mkdir(parents=True)
        (self.skills / "alpha" / "SKILL.md").write_text("---\nname: alpha\n---\nolder plain copy\n")
        (self.skills / "alpha" / "extra-from-old-copy.md").write_text("kept\n")
        self.assertEqual(setup.install_skills(self.root, self.home)[0][0], "ok")
        self.assertIn("alpha v1", (self.skills / "alpha" / "SKILL.md").read_text())
        self.assertEqual((self.skills / "alpha" / "extra-from-old-copy.md").read_text(), "kept\n")

    def test_extras_download_fit_and_stay_put(self):
        r = setup.install_extras(self.root, self.home)
        self.assertEqual([(t, n) for t, n, _ in r], [("ok", "duo"), ("ok", "seedance-cinematic")])
        duo = self.skills / "duo"
        for rel in setup._DUO + ["LICENSE", "SOURCE.txt"]:
            self.assertTrue((duo / rel).is_file(), rel)
        self.assertEqual((duo / "assets" / "plate.png").read_bytes(), b"\x89fake assets/plate.png")
        self.assertIn("Your own changes (read first", (duo / "SKILL.md").read_text())
        text = (self.skills / "seedance-cinematic" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn('description: "Make film prompts. Triggers on: cinematic, noir.', text)
        self.assertIn('\\"cinematic\\"', text)
        self.assertEqual(setup._skill_name(self.skills / "seedance-cinematic" / "SKILL.md"), "seedance-cinematic")
        self.assertLess(text.index("Your own changes (read first"), text.index("# Seedance"))
        self.assertIn(setup.EXTRAS[1]["commit"], (self.skills / "seedance-cinematic" / "SOURCE.txt").read_text())
        # a second run downloads nothing (the source folder is gone and it still says ok)
        shutil.rmtree(self.extras)
        r = setup.install_extras(self.root, self.home)
        self.assertEqual([t for t, _, _ in r], ["ok", "ok"])
        self.assertIn("already here", r[0][2])

    def test_a_failed_download_is_reported_not_raised(self):
        shutil.rmtree(self.extras)
        r = setup.install_extras(self.root, self.home)
        self.assertEqual([t for t, _, _ in r], ["--", "--"])
        self.assertFalse((self.skills / "duo").exists())

    def test_extras_leave_a_members_own_copy_alone_and_follow_a_new_pin(self):
        (self.skills / "duo").mkdir(parents=True)
        (self.skills / "duo" / "SKILL.md").write_text("---\nname: duo\n---\nmy own copy\n")
        setup.install_extras(self.root, self.home)
        self.assertIn("my own copy", (self.skills / "duo" / "SKILL.md").read_text())
        # the pack's own copy is fetched again when a release moves the pinned commit
        source = self.skills / "seedance-cinematic" / "SOURCE.txt"
        source.write_text("commit 0000\n")
        (self.skills / "seedance-cinematic" / "SKILL.md").write_text("---\nname: seedance-cinematic\n---\nstale\n")
        setup.install_extras(self.root, self.home)
        self.assertIn("# Seedance", (self.skills / "seedance-cinematic" / "SKILL.md").read_text())

    def test_fit_changes_nothing_else(self):
        out = setup._fit(DUO, "## Your own changes (read first, every time)\n\nX.\n")
        self.assertTrue(out.startswith("---\nname: duo\ndescription: >\n  Two screens on a foldable phone.\n---\n"))
        self.assertTrue(out.endswith("# Duo\n\nBody.\n"))
        self.assertEqual(setup._fit(out, "## Your own changes (read first, every time)\n\nX.\n"), out)

    def test_check_files(self):
        self.assertEqual(setup.check_files(self.root), "1.0.0")
        (self.root / "skills" / "beta" / "SKILL.md").write_text("---\nname: wrong\n---\n")
        with self.assertRaises(setup.SetupError):
            setup.check_files(self.root)
        (self.root / "skills" / "beta" / "SKILL.md").write_text("---\nname: beta\n---\n")
        (self.root / "scripts" / "broken.py").write_text("def (:\n")
        with self.assertRaises(setup.SetupError):
            setup.check_files(self.root)
        (self.root / "scripts" / "broken.py").unlink()
        shutil.rmtree(self.root / "skills" / "alpha")          # kit.json lists a skill that is gone
        with self.assertRaises(setup.SetupError):
            setup.check_files(self.root)

    def test_this_repo_passes_its_own_check(self):
        self.assertEqual(setup.check_files(REPO), (REPO / "VERSION").read_text().strip())
        block = (REPO / setup.BLOCK).read_text(encoding="utf-8").strip()
        for name in setup.shipped_skills(REPO):
            text = (REPO / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn(block, text, name)
            self.assertTrue((REPO / "skills" / name / "LICENSE").is_file(), name)
        for extra in setup.EXTRAS:                              # never shipped, only downloaded
            self.assertFalse((REPO / "skills" / extra["name"]).exists(), extra["name"])


if __name__ == "__main__":
    unittest.main()
