#!/usr/bin/env python3
"""Finish (or refresh) a Video Pro Pack install. Safe to run again at any time.

    <python> scripts/setup.py            copy the skills into Claude Code, fetch the extras, then check
    <python> scripts/setup.py --after    the same, quietly (the auto-updater runs this after an update)
    <python> scripts/setup.py --check    only check; changes nothing

Run from the installed folder (~/solnest/video-pro-pack), where <python> is bin/py.

What it does:
  skills   copies each folder in skills/ to ~/.claude/skills/<name>/. Only files the pack
           ships are written, and only files an earlier copy of the pack put there are
           removed, so anything else in that folder (node_modules from a skill's own
           setup, a file the member added) stays. A skill folder that is a link, a git
           checkout or a different skill is left alone and reported.
  extras   downloads the two skills this repo does not ship (see THIRD_PARTY_NOTICES.md
           for why) straight from their own repos, each pinned to one reviewed commit.
           Optional: a failed download is reported and setup goes on.
  check    proves the files load and says what else is on this computer (HyperFrames,
           Node, ffmpeg). Read-only.

Standard library only. VIDEO_PRO_PACK_EXTRAS_DIR=<folder> reads the extras from that
folder instead of GitHub (offline tests only).
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KIT = "video-pro-pack"
LABEL = "Video Pro Pack"
MARK = ".video-pro-pack-skill.txt"   # inside each installed skill: the files this pack put there
LOCAL_EXTRAS = "VIDEO_PRO_PACK_EXTRAS_DIR"
UA = {"User-Agent": "solnest-video-pro-pack-setup"}
NODE_MIN = 22
BLOCK = "scripts/own-changes-block.md"
# Never copied into a skill folder, never removed from one.
SKIP_DIRS = {".git", ".cursor", "node_modules", "__pycache__", ".venv", "venv", ".cache", ".pytest_cache"}
SKIP_NAMES = {".DS_Store", "Thumbs.db", MARK}

# Skills that are not in this repo, downloaded from their own repos. Pinned to a commit,
# so a member never gets a version nobody here has looked at. To move to a newer one,
# change the commit in a release. Why each one is not shipped: THIRD_PARTY_NOTICES.md.
_DUO = ["SKILL.md", "assets/icons-instagram.svg", "assets/icons-tiktok.svg", "assets/plate-preview.jpg",
        "assets/plate.png", "assets/screen-spec.json", "references/feed-recipes.md",
        "references/screen-geometry.md", "references/sourcing-real-ui.md", "scripts/build.mjs",
        "template/index.template.html"]
EXTRAS = [
    {"name": "duo",
     "what": "two screens side by side on a foldable phone",
     "repo": "heygen-com/hyperframes-community-skills",
     "commit": "ba7a0bb6d3567d124c51f6074625043bfe0b32eb",
     "files": {**{f"skills/duo/{rel}": rel for rel in _DUO}, "LICENSE": "LICENSE"}},
    {"name": "seedance-cinematic",
     "what": "film-style prompt writer for Seedance 2.0 on Higgsfield",
     "repo": "beshuaxian/higgsfield-seedance2-jineng",
     "commit": "83dcb10ee38c9694ac0f455ec55a62f2be3b8a14",
     "files": {"skills/01-cinematic/SKILL.md": "SKILL.md"}},
]


class SetupError(RuntimeError):
    """Something a member (or Claude) has to act on."""


def say(tag: str, label: str, text: str) -> None:
    print(f"[{tag}] {label:<9} {text}", flush=True)


def skills_home(home: Path | None = None) -> Path:
    return (home or Path.home()) / ".claude" / "skills"


def shipped_skills(root: Path = ROOT) -> list[str]:
    folder = root / "skills"
    return sorted(p.name for p in folder.iterdir() if (p / "SKILL.md").is_file()) if folder.is_dir() else []


def _skill_name(skill_md: Path) -> str | None:
    """The name: line of a SKILL.md's front matter, or None."""
    try:
        head = skill_md.read_text(encoding="utf-8", errors="replace")[:6000]
    except OSError:
        return None
    m = re.match(r"---\r?\n(.*?)\r?\n---", head, re.S)
    n = re.search(r"^name:\s*[\"']?([A-Za-z0-9_.-]+)[\"']?\s*$", m.group(1) if m else head, re.M)
    return n.group(1) if n else None


def _files(src: Path) -> dict[str, Path]:
    out = {}
    for path in sorted(src.rglob("*")):
        rel = path.relative_to(src)
        if (path.is_file() and not path.is_symlink() and path.name not in SKIP_NAMES
                and not any(part in SKIP_DIRS for part in rel.parts[:-1])
                and not (path.name == ".env" or (path.name.startswith(".env.") and path.name != ".env.example"))):
            out[rel.as_posix()] = path
    return out


def _marked(dest: Path) -> list[str]:
    try:
        lines = (dest / MARK).read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return []
    return [ln for ln in lines if ln and not ln.startswith("#") and ".." not in Path(ln).parts
            and not ln.startswith(("/", "\\"))]


def _refuse(dest: Path, name: str) -> str | None:
    """Why this folder must be left alone, or None when the pack may write there."""
    if dest.is_symlink():
        return "is a link, so another installer manages it. Left alone"
    if dest.exists() and not dest.is_dir():
        return "is a file, not a folder. Left alone"
    if (dest / ".git").exists():
        return "is a git checkout (a developer's copy). Left alone"
    if (dest / "SKILL.md").is_file() and _skill_name(dest / "SKILL.md") not in (name, None):
        return "holds a different skill. Left alone"
    return None


def _put(dest: Path, name: str, files: dict[str, bytes]) -> None:
    """Write one skill's files, drop the ones an earlier copy of the pack put there and
    this one no longer has, then record the list."""
    before = _marked(dest)
    for rel, data in files.items():
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(target.name + ".setup-tmp")
        tmp.write_bytes(data)
        os.replace(tmp, target)
        if rel.endswith((".sh", ".mjs", ".py")):
            with contextlib.suppress(OSError):
                target.chmod(target.stat().st_mode | 0o755)
    for rel in before:
        if rel not in files and (dest / rel).is_file():
            (dest / rel).unlink()
            parent = (dest / rel).parent
            while parent != dest and parent.is_dir() and not any(parent.iterdir()):
                parent.rmdir()
                parent = parent.parent
    (dest / MARK).write_text(f"# Files the {LABEL} put in this skill folder (scripts/setup.py). Do not edit.\n"
                             + "\n".join(sorted(files)) + "\n", encoding="utf-8")


def install_skills(root: Path = ROOT, home: Path | None = None) -> list[tuple[str, str, str]]:
    """[(tag, name, message)] for every skill the pack ships."""
    results = []
    for name in shipped_skills(root):
        dest = skills_home(home) / name
        why = _refuse(dest, name)
        if why:
            results.append(("--", name, f"{dest} {why}"))
            continue
        files = {rel: path.read_bytes() for rel, path in _files(root / "skills" / name).items()}
        try:
            _put(dest, name, files)
        except OSError as e:
            results.append(("!!", name, f"could not be copied ({type(e).__name__}: {e})"))
            continue
        results.append(("ok", name, f"{len(files)} file(s)"))
    return results


# ── The extras: other authors' skills, from their own repos ────────────
def _get(url: str, timeout: float = 60) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


def _fit(text: str, block: str) -> str:
    """Make a downloaded SKILL.md load here: quote a description that has a colon in it
    (Claude Code cannot read the front matter otherwise) and add the member's
    "Your own changes" section under the front matter. Nothing else is changed."""
    text = text.replace("\r\n", "\n")
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if not m:
        return text
    head = []
    for line in m.group(1).split("\n"):
        d = re.match(r"description:\s*(.*)$", line)
        if d and d.group(1) and d.group(1)[0] not in "\"'|>" and ": " in d.group(1):
            line = "description: " + json.dumps(d.group(1).strip(), ensure_ascii=False)
        head.append(line)
    body = text[m.end():].lstrip("\n")
    if block and "Your own changes (read first" not in body:
        body = block.strip("\n") + "\n\n" + body
    return "---\n" + "\n".join(head) + "\n---\n\n" + body


def install_extras(root: Path = ROOT, home: Path | None = None, refresh: bool = False) -> list[tuple[str, str, str]]:
    """[(tag, name, message)]. Never raises for a failed download: every extra is optional."""
    results = []
    local = os.environ.get(LOCAL_EXTRAS)
    try:
        block = (root / BLOCK).read_text(encoding="utf-8")
    except OSError:
        block = ""
    for extra in EXTRAS:
        name = extra["name"]
        dest = skills_home(home) / name
        why = _refuse(dest, name)
        if why:
            results.append(("--", name, f"{dest} {why}"))
            continue
        if (dest / "SKILL.md").is_file() and not refresh:
            # Someone else's copy is left as it is. Ours is fetched again only when a
            # release moved the pinned commit.
            try:
                source = (dest / "SOURCE.txt").read_text(encoding="utf-8", errors="replace")
            except OSError:
                source = ""
            if not (dest / MARK).is_file() or extra["commit"] in source:
                results.append(("ok", name, f"already here ({extra['what']})"))
                continue
        files: dict[str, bytes] = {}
        try:
            for src, rel in extra["files"].items():
                data = (Path(local) / extra["repo"].replace("/", "__") / src).read_bytes() if local else \
                    _get(f"https://raw.githubusercontent.com/{extra['repo']}/{extra['commit']}/{src}")
                files[rel] = data
            skill = _fit(files["SKILL.md"].decode("utf-8"), block)
            if not re.search(rf"^name:\s*{re.escape(name)}\s*$", skill[:2000], re.M):
                raise ValueError("the download is not the skill that was expected")
            files["SKILL.md"] = skill.encode("utf-8")
        except (OSError, ValueError, KeyError, urllib.error.URLError) as e:
            results.append(("--", name, f"could not be downloaded ({type(e).__name__}). Optional: "
                                        f"every other skill works without it"))
            continue
        files["SOURCE.txt"] = (
            f"Downloaded by the {LABEL} setup from https://github.com/{extra['repo']}\n"
            f"commit {extra['commit']}\nThis skill belongs to its author. Setup quoted the description "
            f"line and added the \"Your own changes\" section. See THIRD_PARTY_NOTICES.md in the pack.\n"
        ).encode("utf-8")
        try:
            _put(dest, name, files)
        except OSError as e:
            results.append(("--", name, f"could not be saved ({type(e).__name__})"))
            continue
        results.append(("ok", name, f"downloaded from github.com/{extra['repo']}"))
    return results


# ── Check (read-only) ──────────────────────────────────────────────────
def check_files(root: Path = ROOT) -> str:
    """The shipped files load. A release that fails this must not stay installed."""
    try:
        kit = json.loads((root / "kit.json").read_text(encoding="utf-8"))
        version = (root / "VERSION").read_text(encoding="utf-8").strip()
        runbook = (root / "CLAUDE.md").read_text(encoding="utf-8")
    except (OSError, ValueError) as e:
        raise SetupError(f"a pack file does not load ({type(e).__name__}: {e})") from e
    if not isinstance(kit, dict) or kit.get("kit") != KIT:
        raise SetupError(f"kit.json is not the {LABEL}'s")
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise SetupError("VERSION is not a version number")
    if "## SETUP" not in runbook:
        raise SetupError("CLAUDE.md has no SETUP section")
    want = kit.get("skills")
    have = shipped_skills(root)
    if not isinstance(want, list) or not want or sorted(want) != have:
        raise SetupError(f"the skills folder does not match kit.json (found: {', '.join(have) or 'none'})")
    for name in have:
        if _skill_name(root / "skills" / name / "SKILL.md") != name:
            raise SetupError(f"skills/{name}/SKILL.md has no matching name line")
    for py in sorted((root / "scripts").glob("*.py")):
        try:
            compile(py.read_bytes(), str(py), "exec")
        except (SyntaxError, ValueError) as e:
            raise SetupError(f"scripts/{py.name} does not parse ({e})") from e
    return version


def hyperframes_found() -> str | None:
    """Where the official HyperFrames plugin or skill is installed, or None. Read-only."""
    cfg = Path(os.environ.get("CLAUDE_CONFIG_DIR") or (Path.home() / ".claude")).expanduser()
    try:
        data = json.loads((cfg / "plugins" / "installed_plugins.json").read_text(encoding="utf-8"))
        for name in (data.get("plugins") or {}):
            if name.split("@")[0] == "hyperframes":
                return f"plugin {name}"
    except (OSError, ValueError, AttributeError):
        pass
    for folder in (cfg / "skills" / "hyperframes", Path.home() / ".claude" / "skills" / "hyperframes",
                   Path.home() / ".agents" / "skills" / "hyperframes"):
        if (folder / "SKILL.md").is_file():
            return f"skill folder {folder}"
    return None


def node_major() -> int | None:
    node = shutil.which("node")
    if not node:
        return None
    try:
        out = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.match(r"v?(\d+)\.", out.strip())
    return int(m.group(1)) if m else None


def report_computer() -> None:
    """Information only: none of these lines can fail setup or undo an update."""
    base = hyperframes_found()
    say("ok" if base else "--", "hyperframes", base or "not installed yet (five of the skills need it)")
    major = node_major()
    if major is None:
        say("--", "node", f"not found (the animation skills need Node.js {NODE_MIN} or newer)")
    else:
        say("ok" if major >= NODE_MIN else "--", "node",
            f"version {major}" + ("" if major >= NODE_MIN else f" (the animation skills need {NODE_MIN} or newer)"))
    ffmpeg = shutil.which("ffmpeg")
    say("ok" if ffmpeg else "--", "ffmpeg", ffmpeg or "not found (needed to save a video file)")


# ── Commands ───────────────────────────────────────────────────────────
def run_all(after: bool = False) -> int:
    version = check_files()
    say("ok", "files", f"version {version} loads")
    results = install_skills()
    for tag, name, message in results:
        say(tag, "skill", f"{name}: {message}")
    for tag, name, message in install_extras():
        say(tag, "extra", f"{name}: {message}")
    if not after:
        report_computer()
    if any(tag == "!!" for tag, _, _ in results) or not any(tag == "ok" for tag, _, _ in results):
        raise SetupError("no skill could be copied into Claude Code. Read the lines above")
    return 0


def run_check() -> int:
    version = check_files()
    say("ok", "files", f"version {version} loads")
    rc = 0
    for name in shipped_skills() + [e["name"] for e in EXTRAS]:
        dest = skills_home() / name
        optional = name not in shipped_skills()
        if (dest / "SKILL.md").is_file() and _skill_name(dest / "SKILL.md") == name:
            ours = (dest / MARK).is_file()
            say("ok", "skill", f"{name}: installed" + ("" if ours else " (not by this pack, left as it is)"))
        else:
            say("--", "skill", f"{name}: not installed" + (" (optional)" if optional else ""))
            rc = rc if optional else 1
    report_computer()
    return rc


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        with contextlib.suppress(AttributeError, ValueError):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=f"Finish or refresh a {LABEL} install.")
    ap.add_argument("--after", action="store_true", help="refresh quietly after an update")
    ap.add_argument("--check", action="store_true", help="only check; changes nothing")
    args = ap.parse_args()
    try:
        return run_check() if args.check else run_all(after=args.after)
    except SetupError as e:
        print(f"[!!] {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
