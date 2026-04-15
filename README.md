# procmon skill

A Claude Code skill for driving Microsoft Sysinternals **Process Monitor** (`procmon`) from the command line — capture Windows process/file/registry/network activity, filter it, and export to CSV for inspection.

## What this repo contains

- `SKILL.md` — the skill definition. Drop it into `~/.claude/skills/procmon/` (or equivalent) so Claude Code can invoke procmon on your behalf.

This repo does **not** ship the procmon binaries. Download them from Microsoft:
<https://learn.microsoft.com/sysinternals/downloads/procmon>

## Installing the skill

```bash
mkdir -p ~/.claude/skills/procmon
cp SKILL.md ~/.claude/skills/procmon/
```

On Windows:

```powershell
mkdir $env:USERPROFILE\.claude\skills\procmon
copy SKILL.md $env:USERPROFILE\.claude\skills\procmon\
```

Restart Claude Code so it picks up the new skill.

## What it's good for

- Diagnosing "file not found" / `ACCESS DENIED` errors on Windows
- Figuring out which config file or registry key a program is actually reading
- Capturing a short trace of a hung or slow process and converting it to CSV
- Scripting unattended procmon captures in CI or a repro harness

See `SKILL.md` for command-line recipes and analysis tips.

## License

MIT — see `LICENSE`. Procmon itself is Microsoft's and is covered by the Sysinternals EULA; this repo does not redistribute it.
