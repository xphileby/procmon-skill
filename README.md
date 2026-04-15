# procmon-skill

A Claude Code skill for capturing Windows activity with Microsoft Sysinternals **Process Monitor** (procmon) and analyzing it to find out which processes are hammering the disk, what paths they touch, and whether anything is crash-looping.

## What's in this repo

```
.
├── .claude/
│   └── skills/
│       └── procmon/
│           └── SKILL.md          Skill definition (auto-loaded by Claude Code)
├── tools/
│   ├── analyze_csv.py            Streaming FS-activity analyzer
│   └── svchost_drill.py          Per-PID drill-down for noisy svchost.exe
├── README.md
└── LICENSE
```

## Quick start

```bash
git clone https://github.com/xphileby/procmon-skill
cd procmon-skill
claude                                   # open Claude Code in the repo
```

Claude Code auto-discovers `.claude/skills/procmon/SKILL.md`, so the skill is active immediately — no copying into `~/.claude/` required. Ask Claude something like *"capture a 10-minute procmon trace and tell me what's eating my disk"* and it will drive the flow below.

You still need to install Procmon itself (not redistributed here): <https://learn.microsoft.com/sysinternals/downloads/procmon>.

## Sampling flow

Ten-step procedure for a clean capture + analysis. All commands assume an elevated (admin) shell and a `<staging_dir>` you pick (default `C:\Users\<user>\procmon_logs`).

### 1. Pick a duration and staging directory

5 / 10 / 15 minutes covers most investigations (10 min is the sweet spot).

### 2. Clean the staging directory

```bash
mkdir -p <staging_dir>
rm -f <staging_dir>/*.pml <staging_dir>/*.csv
```

### 3. Start Procmon detached with auto-terminate

Use PowerShell `Start-Process` — bash `&` ties the child to the shell and kills it on exit.

```bash
powershell -NoProfile -Command "Start-Process -FilePath 'C:\Program Files\procmon\Procmon64.exe' \
  -ArgumentList '/Quiet','/Minimized','/AcceptEula','/BackingFile','<staging_dir>\cap.pml','/Runtime','<seconds>' \
  -WindowStyle Hidden"
```

`/Runtime N` auto-terminates cleanly after N seconds. **Always use it** — killing Procmon manually leaves a truncated PML.

### 4. Wait for auto-termination

```bash
sleep $((duration_seconds + 20))
```

The extra 20 s covers Procmon's process-table flush at shutdown.

### 5. Verify a clean close

```bash
tasklist //FI "IMAGENAME eq Procmon64.exe"
ls -lh <staging_dir>/
```

Expect no `Procmon64.exe` running; one `cap.pml` on disk (plus `cap-1.pml`, `cap-2.pml`, … if the capture rotated at the 4 GB file-size limit).

### 6. Convert PML → CSV via Procmon

```bash
powershell -NoProfile -Command "Start-Process -FilePath 'C:\Program Files\procmon\Procmon64.exe' \
  -ArgumentList '/OpenLog','<staging_dir>\cap.pml','/SaveAs','<staging_dir>\cap.csv','/AcceptEula' \
  -WindowStyle Hidden -Wait"
```

`-Wait` blocks until conversion is done (~1 min per GB of PML). Repeat for each rotated `cap-N.pml`.

> The `procmon-parser` PyPI library cannot read rotated PMLs. Convert to CSV via Procmon itself, then analyze.

### 7. Run the main analyzer

```bash
python tools/analyze_csv.py <staging_dir>/cap.csv
```

Multi-file (rotated) captures:

```bash
python tools/analyze_csv.py <staging_dir>/cap.csv <staging_dir>/cap-1.csv
```

Output: top 25 processes by FS op count, overall operation mix, per-process operation breakdown, and sampled hot paths for the top 5 offenders.

### 8. Interpret

- `Procmon64.exe` is always #1 (~45 %, self-observation noise). Ignore it.
- Empty process name = kernel / `System`.
- `WerFault.exe` + `WerSvc` writing `C:\ProgramData\Microsoft\Windows\WER\Temp\WER.*.tmp.csv` = something is crash-looping.
- `svchost.exe` as a top offender means nothing on its own — go to step 9.

### 9. Drill into noisy svchost (optional)

```bash
python tools/svchost_drill.py <staging_dir>/cap.csv
```

Then map each noisy PID → service name, while the PID is still alive:

```bash
tasklist //SVC //FI "PID eq <PID>"
```

### 10. Crash-loop triage (only if step 8 flagged WER)

```bash
ls /c/ProgramData/Microsoft/Windows/WER/ReportArchive/ | \
  sed 's/_[a-f0-9-]*$//' | sort | uniq -c | sort -rn | head -10
```

Counts recent WER reports grouped by crashing-app name. Dozens of `AppCrash_<binary>_*` entries in the last hour → that binary is your crash-looper.

## Script reference

Both scripts are pure-stdlib Python 3. They stream the CSV row-by-row, so multi-GB captures analyze in a minute or two.

### `tools/analyze_csv.py`

```
python tools/analyze_csv.py <csv_path> [<csv_path> ...]
```

Ranked per-process filesystem-activity report. FS events are identified by exclusion — any `Operation` that doesn't start with `Reg`, `TCP`, `UDP`, `Thread `, `Process `, `Load Image`, or `Profiling` is counted as filesystem.

Sections printed:

- **TOP 25 PROCESSES BY FS OPERATIONS** — process name, op count, % of total FS ops.
- **OPERATION MIX** — top 15 op kinds across the whole trace.
- **PER-PROCESS OPERATION BREAKDOWN** — top 8 ops for each of the top 10 processes.
- **SAMPLED HOT PATHS** — top 6 paths for each of the top 5 processes (1-in-50 sampling to keep memory bounded).

### `tools/svchost_drill.py`

```
python tools/svchost_drill.py <csv_path> [<csv_path> ...]
```

Filters the CSV to `svchost.exe` rows, ranks PIDs by `WriteFile` count, and for the top 3 prints full operation mix, full WriteFile target paths (unsampled), and 1-in-25 sampled all-op hot paths. Also emits the exact `tasklist /SVC` commands to map each PID to its service name.

### Pipeline

```
Procmon capture  →  cap.pml  (+ cap-1.pml, cap-2.pml if rotated)
      │  (Procmon /OpenLog ... /SaveAs)
      ▼
   cap.csv  (+ cap-1.csv, ...)
      │
      ├──▶ tools/analyze_csv.py   — always run first
      │
      └──▶ tools/svchost_drill.py — only if svchost appears in the
                                     top offenders from analyze_csv
```

Neither script writes files; both print to stdout. Pipe to a file for archiving: `python tools/analyze_csv.py cap.csv > analysis.txt`.

## Using the skill outside this repo

To make the skill available globally (not just when Claude Code is opened in this repo), copy the skill folder into your user-level skills directory:

```bash
# Linux / macOS
cp -r .claude/skills/procmon ~/.claude/skills/
cp -r tools ~/.claude/skills/procmon/

# Windows (PowerShell)
Copy-Item -Recurse .claude\skills\procmon $env:USERPROFILE\.claude\skills\
Copy-Item -Recurse tools $env:USERPROFILE\.claude\skills\procmon\
```

Then update the script paths in `SKILL.md` (change `tools/analyze_csv.py` to `scripts/analyze_csv.py` or whatever you land on) so Claude invokes them from the right place. The repo layout is optimized for the cloned-and-opened case; the global-install case is a secondary path.

## License

MIT — see `LICENSE`.

Procmon itself is Microsoft's and is covered by the Sysinternals EULA; this repo does not redistribute it.
