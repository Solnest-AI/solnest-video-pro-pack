# Third-party notices

The Video Pro Pack is put together by Solnest AI. The skills in it were written by other people. This page says who, under what license, and what Solnest changed.

## Shipped in this repo

| Folder | Author and source | Version | License |
|---|---|---|---|
| `skills/heygen-avatar` | HeyGen, https://github.com/heygen-com/skills | 3.2.0, commit `1bd5e4d33a028dfed3abf504c5e3dd644fb9ea8a` | MIT |
| `skills/heygen-video` | HeyGen, same repo | same | MIT |
| `skills/heygen-translate` | HeyGen, same repo | same | MIT |
| `skills/vox-explainer` | HyperFrames community, https://github.com/heygen-com/hyperframes-community-skills | commit `ba7a0bb6d3567d124c51f6074625043bfe0b32eb` | Apache-2.0 |
| `skills/camera-3d-captions` | HyperFrames community, same repo | same | Apache-2.0 |
| `skills/session-story` | HyperFrames community, same repo | same | Apache-2.0 |
| `skills/day-in-my-life` | HyperFrames community, same repo | same | Apache-2.0 |

Each folder carries the full license text of its source repo in a `LICENSE` file.

Inside `skills/session-story/assets/engine/`, three files are adapted from ClaudeAnimationBase by John Heibel (MIT). The skill's own `NOTICE.md` and `LICENSE-ClaudeAnimationBase` in that folder are kept as published.

### What Solnest changed

One change, the same in every `SKILL.md` above: a section called "Your own changes (read first, every time)" was added right under the front matter. It tells Claude to read the member's own instructions file first. A `LICENSE` file was copied into each skill folder from the root of its source repo. Nothing else was edited.

## Downloaded during setup, not shipped here

| What | Source | Why it is not in this repo |
|---|---|---|
| `duo` skill | https://github.com/heygen-com/hyperframes-community-skills (Apache-2.0), commit `ba7a0bb6d3567d124c51f6074625043bfe0b32eb` | Its background picture is made from a photo someone else posted on X, and it includes TikTok and Instagram icons. The skill says so itself. Solnest does not republish those. Setup downloads the skill from HeyGen's repo to the member's computer. |
| `seedance-cinematic` skill | https://github.com/beshuaxian/higgsfield-seedance2-jineng, commit `83dcb10ee38c9694ac0f455ec55a62f2be3b8a14`, file `skills/01-cinematic/SKILL.md` | That repo has no license file. Its contributing guide says MIT, but the license itself is missing, so Solnest does not ship a copy. Setup downloads it from that repo to the member's computer. |
| HyperFrames | HeyGen, https://github.com/heygen-com/hyperframes (Apache-2.0) | It is HeyGen's plugin. Setup installs it from HeyGen's own marketplace, and it updates through HeyGen. |

On the member's computer, setup makes two small changes to a downloaded `SKILL.md` so it loads and follows the member's own instructions: it puts quotes around a description line that has a colon in it, and it adds the same "Your own changes" section. A `SOURCE.txt` file next to it records where it came from.

## Fetched by the skills themselves

Some skills download packages the first time they are used (for example p5, p5.brush, puppeteer, GSAP from a CDN, and the HyperFrames command line tool from npm). Each skill's `SKILL.md` lists what it fetches and under which license. None of that code is in this repo.

## Names

HeyGen, HyperFrames, Higgsfield, Seedance, Vox, TikTok, Instagram and X are names of their owners. This pack is not made or endorsed by any of them.
