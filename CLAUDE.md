If the user said "set this up", follow SETUP below.

# Video Pro Pack (Solnest AI)

This repo installs nine video skills for Claude Code in one go, plus the HyperFrames plugin five of them are built on.

| Skill | What it does | Needs |
|---|---|---|
| `heygen-avatar` | Builds a reusable avatar (a face and a voice) in HeyGen | HeyGen account |
| `heygen-video` | Makes a presenter video from a topic or a script | HeyGen account |
| `heygen-translate` | Dubs a finished video into other languages, with lip sync | HeyGen account |
| `vox-explainer` | Builds a 60 to 90 second collage-style explainer video | HyperFrames |
| `duo` | Puts two screens side by side on a foldable phone, for comparison videos | HyperFrames |
| `camera-3d-captions` | Puts captions in 3D space around a talking head | HyperFrames |
| `session-story` | Animates a typical work session between the user and Claude | HyperFrames |
| `day-in-my-life` | Draws an ink film of "a day in my life as your agent" | HyperFrames |
| `seedance-cinematic` | Writes film-style prompts for Seedance 2.0 on Higgsfield | Higgsfield account to use the prompts |

What is in here:
- `skills/`: seven of the skills, as their authors published them (HeyGen and the HyperFrames community, MIT and Apache-2.0 licenses, see `THIRD_PARTY_NOTICES.md`). Setup copies each one to `~/.claude/skills/<name>`.
- `duo` and `seedance-cinematic` are not in this repo. Setup downloads each one from its own repo instead of shipping a copy. `THIRD_PARTY_NOTICES.md` says why.
- HyperFrames is not in this repo either. Setup installs it from HeyGen's own plugin marketplace.
- `install.sh`, `scripts/setup.py`: the installer and the setup script. `VERSION` and `CHANGELOG.md`: what release this is.
- The pack lives in `~/solnest/video-pro-pack` on the user's computer.

## Your own changes (read first, every time)

Before anything else, read `~/.solnest/video-pro-pack/my-instructions.md` if it exists and
follow it. It holds this user's own changes to how this tool works, and it wins over the
defaults in this file.

When the user asks to change how this tool works for them (wording, tone, topics, steps,
defaults, what to include or leave out), write the change into that file in plain words,
create it if needed, and read it back to them. **Never edit this tool's own files for
that.** This tool updates itself automatically and replaces its own files, so a change
made there is lost on the next update. This pack keeps no keys file. Their HeyGen sign-in,
their saved avatar files (`AVATAR-*.md`), their video project folders, and anything a
skill's own setup installed inside its folder (like `node_modules`) are never touched by
an update either.

## Rules for you (Claude)

- You run every command yourself with your Bash tool. The user never opens a terminal. On Windows, Claude Code runs Bash commands in Git Bash, where these commands (including `~`) work.
- One step per message. Do not report success until you have seen real output.
- Never ask for a key or a password in chat. HeyGen connects through a browser sign-in. Nothing in this pack needs a key.
- Never install a program on the user's computer without a plain yes from them in chat first.
- Making a HeyGen video, an avatar or a translation uses the user's HeyGen credits. Seedance clips on Higgsfield cost credits too. Before anything that spends credits, show what you are about to make and ask "make this?". A plain yes is enough. Never test a connection by making a video.
- `session-story` and `day-in-my-life` read the user's own Claude Code history on this computer. The skills ask first. Keep that step.

## SETUP

### Step 1: Install the pack

Tell the user in one line: "Installing the Video Pro Pack. A minute or two, nothing for you to do." Then run one of these:

- You are reading this from the GitHub page (no local copy of this repo):

  ```bash
  bash -o pipefail -c "curl -fsSL https://raw.githubusercontent.com/Solnest-AI/solnest-video-pro-pack/main/install.sh | bash"
  ```

- You already have this repo as a folder on this computer: `bash "<this folder>/install.sh"`

The installer copies the pack to `~/solnest/video-pro-pack`, finds Python 3.9 or newer (or installs one for this user, no admin rights needed) and writes a small launcher (`bin/py`). Running it again is safe.

Read the checklist it prints:
- Every line starts with `[ok]`: go on.
- `STOP: ...`: something else already lives at `~/solnest/video-pro-pack`. Nothing was changed. Tell the user what you found and ask what they want to do with it. Do not delete it yourself.
- `ERROR: could not download`: usually the network. Run it once more.
- `ERROR: no working Python`: send the user to https://www.python.org/downloads/ (on Windows they must tick "Add python.exe to PATH"). When they say it is installed, run Step 1 again.

### Step 2: Put the skills into Claude Code

```bash
"$HOME/solnest/video-pro-pack/bin/py" "$HOME/solnest/video-pro-pack/scripts/setup.py"
```

It prints one line per skill.
- `[ok] skill`: copied to `~/.claude/skills/<name>`.
- `[--] skill ... Left alone`: the user already has that skill from somewhere else (a link, a git checkout, or a different skill under that name). The pack did not touch it. Tell the user which one. That is fine, it is not an error.
- `[ok] extra` (`duo`, `seedance-cinematic`): downloaded from its own repo. `[--] extra`: the download failed. That skill is optional. Say so, and run this step again later.
- The last three lines (`hyperframes`, `node`, `ffmpeg`) are for Step 3.

### Step 3: HyperFrames, Node.js and ffmpeg

Five of the skills build their video with HyperFrames, HeyGen's free video tool.

- `hyperframes` shows `[--]`: install it from HeyGen's marketplace:

  ```bash
  claude plugin marketplace add heygen-com/hyperframes && claude plugin install hyperframes@hyperframes
  ```

  If the `claude` command is not found, ask the user to type `/plugin` in Claude Code, add the marketplace `heygen-com/hyperframes`, and install `hyperframes` from it.
- `node` shows `[--]`: the animation skills need Node.js 22 or newer. Tell the user and ask: "Want me to install it?" On a plain yes: Mac with Homebrew `brew install node`, Windows `winget install OpenJS.NodeJS.LTS`. Otherwise send them to https://nodejs.org (the LTS button).
- `ffmpeg` shows `[--]`: needed to save a video file. Ask the same way. On a plain yes: Mac with Homebrew `brew install ffmpeg`, Windows `winget install Gyan.FFmpeg`.

The pack is still installed if one of these is missing. Say clearly which one is missing and which skills wait on it. The three HeyGen skills and `seedance-cinematic` need none of them.

### Step 4: Connect HeyGen (only if the user wants the HeyGen skills)

Ask: "Do you have a HeyGen account and want the avatar, video and translate skills connected now?" If no, skip this step. They can ask later.

If yes, check first: `claude mcp list` (it may take a few seconds). If a `heygen` line is there, skip to the check below.

- Claude Code in a terminal: run

  ```bash
  claude mcp add --transport http --scope user heygen https://mcp.heygen.com/mcp/v1/
  ```

  Then ask the user to type `/mcp`, pick `heygen`, choose Authenticate, and finish the sign-in in their browser.
- Claude Code desktop app: ask the user to click the + next to the message box, then Connectors, then Manage connectors, then Add custom connector. Name `heygen`, URL `https://mcp.heygen.com/mcp/v1/` (keep the last slash). They sign in to HeyGen in the browser tab that opens and tell you "connected".

Check (read-only, free): in a new chat, "List my HeyGen avatars." Avatars or voices back means it works. Never check by making a video.

### Step 5: Turn on automatic updates (required, silent)

Run this exactly:

```bash
KIT="$HOME/solnest/video-pro-pack"; "$KIT/bin/py" "$KIT/scripts/solnest_autoupdate.py" register --name video-pro-pack --folder "$KIT" --update '{python} scripts/update.py' --after '{python} scripts/setup.py --after' --undo '{python} scripts/update.py --undo'
```

From now on the pack keeps itself on the latest release with no one asking: once a day, in the background when Claude Code starts, it installs the newest published release and copies the skills into Claude Code again. If a new release does not load, it puts the old one back by itself. Relay the one line it prints. Nothing else to tell them.

### Step 6: Check, and tell the user what worked

```bash
"$HOME/solnest/video-pro-pack/bin/py" "$HOME/solnest/video-pro-pack/scripts/setup.py" --check
```

It only looks, it changes nothing. Give the user a short checklist from the real output: which skills are installed, HyperFrames found or just installed, Node and ffmpeg found or missing, HeyGen connected or skipped, automatic updates on.

Then say: "Quit Claude Code fully and open it again so the new skills load. Then try: Make a 15 second foldable phone video comparing two apps, left screen and right screen."

Other first tries, depending on what they have:
- HeyGen connected: "Show me my HeyGen avatars and voices."
- No accounts at all: "Write me a cinematic Seedance prompt for a slow drone shot over my rental at sunset."

## How the skills fit together

- A skill loads when the user's request matches it. If two could fit, ask which they mean.
- The HyperFrames skills pin their own HyperFrames version inside each `SKILL.md`. Follow the skill.
- `session-story`, `day-in-my-life` and `camera-3d-captions` have a one-time setup of their own (packages for that skill). The skill's `SKILL.md` says when to run it. It installs inside the skill folder, and updates leave it alone.
- HeyGen avatars the user creates are saved as `AVATAR-<NAME>.md` in the folder they are working in, not in this pack.

## Update

Updates install themselves (Step 5). Changes the user asked for live in `~/.solnest/video-pro-pack/my-instructions.md`, outside the pack, so they survive every update.

Only when the user asks to update now:

```bash
KIT="$HOME/solnest/video-pro-pack"; "$KIT/bin/py" "$KIT/scripts/update.py" && "$KIT/bin/py" "$KIT/scripts/setup.py" --after
```

Then run the Step 5 line once more, so a newer auto-updater is picked up. To go back one version:

```bash
KIT="$HOME/solnest/video-pro-pack"; "$KIT/bin/py" "$KIT/scripts/update.py" --undo && "$KIT/bin/py" "$KIT/scripts/setup.py" --after
```

"Is it updating itself?": `"$HOME/solnest/video-pro-pack/bin/py" ~/.solnest/autoupdate.py status`. Use `pause` in place of `status` to stop all automatic updates, and `resume` to turn them back on. If `status` shows the last check failed, offer to update now with the line above.

HyperFrames is separate. It updates through HeyGen's own plugin, not through this pack.

## Repair

Run Step 1, Step 2 and Step 5 again. Files the user added are kept.

## Uninstall

```bash
"$HOME/solnest/video-pro-pack/bin/py" ~/.solnest/autoupdate.py remove --name video-pro-pack
```

Then, after a plain yes from the user, delete `~/solnest/video-pro-pack` and the skill folders the pack installed in `~/.claude/skills` (each one it installed has a `.video-pro-pack-skill.txt` file inside). Leave any skill folder without that file alone. HyperFrames and the HeyGen connection stay unless the user asks to remove them too.
