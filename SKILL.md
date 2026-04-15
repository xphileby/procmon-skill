---
name: procmon
description: Run Microsoft Sysinternals Process Monitor (procmon) from the command line to capture, filter, and analyze Windows process, file, registry, and network activity. Use when the user wants to trace what a process does on Windows, diagnose "file not found" / access-denied / hanging-process issues, or convert an existing .PML trace into CSV/XML for inspection.
---

# Procmon skill

Sysinternals **Process Monitor** (procmon) captures real-time file system, registry, process/thread, and network activity on Windows. This skill drives it from the command line so captures can be scripted, filtered, and converted to a text format you can read.

Procmon is not redistributed by this skill — install it separately from <https://learn.microsoft.com/sysinternals/downloads/procmon> and make sure `Procmon.exe` (or `Procmon64.exe`) is on `PATH`, or invoke it by full path.

## Core invocation

```
Procmon.exe /AcceptEula /Quiet /Minimized /BackingFile <path.pml> [options]
```

Key flags:

| Flag | Purpose |
| --- | --- |
| `/AcceptEula` | Suppress the first-run EULA dialog. Required for unattended use. |
| `/Quiet` | No confirmation dialogs. |
| `/Minimized` | Start minimized to tray. |
| `/BackingFile <file>` | Write capture to this `.PML` file instead of memory. |
| `/LoadConfig <file>` | Load a saved `.pmc` config (filters, columns). |
| `/Runtime <seconds>` | Capture for N seconds then exit. Good for scripted captures. |
| `/Terminate` | Stop a running procmon instance. |
| `/OpenLog <file.pml>` | Open an existing trace file. |
| `/SaveAs <file.csv\|xml>` | Convert the loaded log and exit. Use with `/OpenLog`. |
| `/SaveAs1 <file>` | Same as `/SaveAs` but without the header row. |
| `/Nofilter` | Ignore saved filters — capture everything. |
| `/Nomonitor` | Start with capture disabled. |

## Typical workflows

### 1. Capture everything a command does, then export to CSV

```bash
# Start capture
Procmon.exe /AcceptEula /Quiet /Minimized /BackingFile capture.pml &

# Run the thing you want to trace
./my-program.exe

# Stop capture
Procmon.exe /Terminate

# Convert .pml → .csv for reading/grepping
Procmon.exe /OpenLog capture.pml /SaveAs capture.csv
```

### 2. Time-boxed capture (no separate terminate step)

```bash
Procmon.exe /AcceptEula /Quiet /Minimized /BackingFile capture.pml /Runtime 30
```

### 3. Use a pre-built filter config

Build filters interactively in the GUI (**Filter → Filter…**), save as `.pmc` via **File → Export Configuration**, then replay:

```bash
Procmon.exe /AcceptEula /Quiet /LoadConfig my-filter.pmc /BackingFile capture.pml /Runtime 30
```

## Analyzing a trace

After `/SaveAs capture.csv`, the CSV has columns: `Time of Day, Process Name, PID, Operation, Path, Result, Detail`.

Common investigations:

- **"File not found" bugs** — filter `Result` = `NAME NOT FOUND` and `Operation` starts with `CreateFile`. The `Path` column shows exactly where the program looked.
- **Access denied** — filter `Result` = `ACCESS DENIED`. Combine with the process name to find the offending operation.
- **What a process touched** — filter `Process Name` = `<yours>`, then group by `Operation` or `Path`.
- **Registry access** — filter `Operation` starts with `Reg`. `RegQueryValue` with `NAME NOT FOUND` is often a missing config key.
- **Hung process** — capture with `/Runtime 10` while it's hung; look for repeated operations on the same path or a long gap before the last syscall.

## Gotchas

- Procmon captures a *lot*. Always apply a filter (by process name, path, or operation) before running for more than a few seconds — unfiltered `.pml` files grow by hundreds of MB/minute on a busy box.
- `Procmon.exe` is the 32-bit launcher; it extracts and runs `Procmon64.exe` on 64-bit Windows. Scripts should invoke `Procmon.exe` — Microsoft reserves the right to change the 64-bit name.
- `/Terminate` only stops an instance started from the same path. If you launched from `C:\Tools\Procmon.exe`, terminate from there too.
- The EULA must be accepted *once per user profile*. `/AcceptEula` handles that; otherwise the GUI dialog blocks unattended runs.
- Procmon requires administrator privileges to capture kernel-level events. Launch the shell elevated, or scripts will silently capture nothing.

## References

- Official docs: <https://learn.microsoft.com/sysinternals/downloads/procmon>
- Command-line switches: <https://learn.microsoft.com/sysinternals/downloads/procmon#command-line-options>
