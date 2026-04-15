---
name: procmon-fs-analyze
description: Capture Windows filesystem/registry/network activity with Sysinternals Procmon and analyze it to find which processes are hammering the disk, what paths they touch, and whether anything is crash-looping. Use when the user reports slow disk, unexplained I/O, a process misbehaving, mysterious "file not found" / "access denied" errors, or asks "what is X doing on my system?". Produces a ranked per-process filesystem report and (optionally) a drill-down on noisy svchost.exe PIDs.
---

# Procmon filesystem-activity skill

Drives Sysinternals **Process Monitor** to capture a timed trace of Windows process/file/registry/network activity, converts it to CSV, and runs the bundled Python analyzers to produce a human-readable report.

The analysis scripts live in `tools/` relative to the repo root (the directory Claude Code is opened in). Invoke them as `python tools/analyze_csv.py <csv>` and `python tools/svchost_drill.py <csv>`.

## Prerequisites

- Windows. `python` on `PATH`. ≥ 5 GB free on the staging drive.
- Procmon binary. Resolve it in this order:
  1. `C:\Program Files\procmon\Procmon64.exe`
  2. `C:\Sysinternals\Procmon64.exe`
  3. `C:\Tools\Sysinternals\Procmon64.exe`
  4. `where.exe Procmon64.exe`
  5. Download <https://download.sysinternals.com/files/ProcessMonitor.zip> and extract.

Admin / elevated shell is required for kernel-level capture.

## Sampling flow

Ten steps end-to-end. Don't skip the auto-terminate (`/Runtime`) — killing Procmon manually leaves a truncated PML that `procmon-parser` chokes on.

### Step 1 — Ask the user for duration and staging location

Defaults: **5 / 10 / 15 minutes** (10 min recommended for most investigations); staging directory `C:\Users\<user>\procmon_logs`.

### Step 2 — Clean the staging directory

```bash
mkdir -p <staging_dir>
rm -f <staging_dir>/*.pml <staging_dir>/*.csv
```

### Step 3 — Start Procmon detached with auto-terminate

Critical: use PowerShell `Start-Process`, **not** bash `&` — a backgrounded child dies when the shell exits.

```bash
powershell -NoProfile -Command "Start-Process -FilePath 'C:\Program Files\procmon\Procmon64.exe' \
  -ArgumentList '/Quiet','/Minimized','/AcceptEula','/BackingFile','<staging_dir>\cap.pml','/Runtime','<seconds>' \
  -WindowStyle Hidden"
```

| Flag | Purpose |
| --- | --- |
| `/Runtime N` | Auto-terminate cleanly after N seconds. **Always use this.** |
| `/Quiet /Minimized /AcceptEula` | No UI, no prompts. |
| `/BackingFile` | Write to disk (not memory) — required for large captures. |

### Step 4 — Wait for auto-termination

```bash
sleep $((duration_seconds + 20))
```

The extra 20 s covers Procmon's process-table flush at shutdown.

### Step 5 — Verify a clean close

```bash
tasklist //FI "IMAGENAME eq Procmon64.exe"
ls -lh <staging_dir>/
```

Expected: no `Procmon64.exe` running; one `cap.pml` on disk (plus `cap-1.pml`, `cap-2.pml` … if the capture rotated at the 4 GB PML file-size limit).

### Step 6 — Convert PML → CSV via Procmon itself

**Do not** use the `procmon-parser` Python library for this — it fails on rotated/rolled-off PMLs. Let Procmon convert:

```bash
powershell -NoProfile -Command "Start-Process -FilePath 'C:\Program Files\procmon\Procmon64.exe' \
  -ArgumentList '/OpenLog','<staging_dir>\cap.pml','/SaveAs','<staging_dir>\cap.csv','/AcceptEula' \
  -WindowStyle Hidden -Wait"
```

`-Wait` blocks until the conversion finishes (~1 min per GB of PML). Repeat for each `cap-N.pml` if the capture rotated.

### Step 7 — Run the main analyzer

```bash
python tools/analyze_csv.py <staging_dir>/cap.csv
```

Pass every rotated CSV if there are more than one:

```bash
python tools/analyze_csv.py <staging_dir>/cap.csv <staging_dir>/cap-1.csv
```

Output (to stdout): top 25 processes by FS op count, overall operation mix, per-process operation breakdown, and a sampled hot-path list for the top 5 offenders. Pipe to a file for later review: `python tools/analyze_csv.py cap.csv > analysis.txt`.

### Step 8 — Interpret

- **`Procmon64.exe` is always #1** (~45 %, self-observation noise). Ignore it.
- **Empty process name** = kernel / `System`.
- **`WerFault.exe` + `WerSvc` writing `C:\ProgramData\Microsoft\Windows\WER\Temp\WER.*.tmp.csv`** = something is crash-looping and Windows Error Reporting is dumping the crash metadata.
- **`svchost.exe` as a top offender** means nothing on its own — svchost hosts dozens of services. Go to step 9 to pinpoint which one.

### Step 9 — Drill into noisy svchost (optional)

```bash
python tools/svchost_drill.py <staging_dir>/cap.csv
```

Prints per-PID WriteFile counts, operation mix, and target paths. Then map each noisy PID to the service name **while the PID is still alive**:

```bash
tasklist //SVC //FI "PID eq <PID>"
```

### Step 10 — Crash-loop triage (only if step 8 flagged WER)

```bash
ls /c/ProgramData/Microsoft/Windows/WER/ReportArchive/ | sed 's/_[a-f0-9-]*$//' | sort | uniq -c | sort -rn | head -10
```

Counts recent WER reports grouped by crashing-app name. If you see dozens of `AppCrash_<binary>_*` entries in the last hour, that binary is your crash-looper.

## Script details

Both analyzers are pure-stdlib Python 3. They stream the CSV row-by-row (never load the whole file), so multi-GB captures analyze in a minute or two.

### `tools/analyze_csv.py`

```
python tools/analyze_csv.py <csv_path> [<csv_path> ...]
```

- **FS classification**: anything whose `Operation` doesn't start with `Reg`, `TCP`, `UDP`, `Thread `, `Process `, `Load Image`, or `Profiling` is treated as filesystem.
- **Hot-path sampling**: records every 50th FS event's path (full per-event path tracking would balloon memory on multi-GB traces).
- **Progress**: prints a heartbeat every 500 000 rows.

### `tools/svchost_drill.py`

```
python tools/svchost_drill.py <csv_path> [<csv_path> ...]
```

- Filters to `svchost.exe` rows only, then ranks PIDs by `WriteFile` count.
- Top 3 PIDs get full WriteFile target paths (unsampled) + all-op hot paths (1-in-25 sample).
- Prints the exact `tasklist /SVC` commands you need to run to map PID → service.

## Expected CSV schema

Procmon's `/SaveAs` export has this header (UTF-8 with BOM):

```
"Time of Day","Process Name","PID","Operation","Path","Result","Detail"
```

The scripts use `encoding="utf-8-sig"` to strip the BOM automatically.

## Common pitfalls

- **Don't kill Procmon manually** — the PML header never gets finalized and the file can't be parsed. Always use `/Runtime`.
- **Don't background with `&` from bash** — the child is tied to the shell lifetime. Use `Start-Process`.
- **PML rotation at 4 GB** is automatic; expect `cap-1.pml`, `cap-2.pml`, … for long captures or busy boxes. Convert and analyze all of them.
- **The `procmon-parser` PyPI library doesn't handle rotated files.** Stick to the Procmon → CSV route.
- **Unfiltered captures grow fast** — a busy dev box produces ~200 MB/min. For anything over 15 min, build a filter interactively in the Procmon GUI and export as `.pmc`, then add `/LoadConfig my-filter.pmc` to the step-3 command line.

## References

- Procmon command-line reference: <https://learn.microsoft.com/sysinternals/downloads/procmon#command-line-options>
- WER report location: <https://learn.microsoft.com/windows/win32/wer/windows-error-reporting>
