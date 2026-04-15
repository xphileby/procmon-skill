"""Streaming analyzer for Procmon CSV exports.

Usage:
    python analyze_csv.py <csv_path> [<csv_path> ...]

Produces a ranked per-process report of filesystem operations: top processes,
operation mix, per-process operation breakdown, and sampled hot paths.

Filesystem events are identified by exclusion: anything whose Operation column
doesn't start with a known non-FS prefix (Reg, TCP, UDP, Thread, Process,
Load Image, Profiling) is treated as FS.
"""

import csv
import sys
import time
from collections import Counter, defaultdict

NON_FS_PREFIXES = ("Reg", "TCP", "UDP", "Thread ", "Process ", "Load Image", "Profiling")


def analyze(paths):
    proc_count = Counter()
    op_count = Counter()
    proc_op = defaultdict(Counter)
    proc_paths = defaultdict(Counter)
    total = 0
    fs_total = 0
    t0 = time.time()

    for path in paths:
        print(f"Reading {path}...", flush=True)
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f)
            next(reader)  # header: Time, Process Name, PID, Operation, Path, Result, Detail
            for row in reader:
                total += 1
                if len(row) < 5:
                    continue
                op = row[3]
                if op.startswith(NON_FS_PREFIXES):
                    continue
                fs_total += 1
                pname = row[1]
                pth = row[4]
                proc_count[pname] += 1
                op_count[op] += 1
                proc_op[pname][op] += 1
                if fs_total % 50 == 0 and pth:
                    proc_paths[pname][pth[:160]] += 1
                if total % 500_000 == 0:
                    dt = time.time() - t0
                    print(
                        f"  rows={total:,} FS={fs_total:,} t={dt:.0f}s "
                        f"rate={total/max(1,dt):.0f}/s",
                        flush=True,
                    )

    dt = time.time() - t0
    print(f"\nRows: {total:,} | FS events: {fs_total:,} | time: {dt:.0f}s\n")

    print("=== TOP 25 PROCESSES BY FS OPERATIONS ===")
    print(f"{'Process':<45} {'FS ops':>12} {'% of FS':>8}")
    for name, n in proc_count.most_common(25):
        pct = 100.0 * n / max(1, fs_total)
        print(f"{name:<45} {n:>12,} {pct:>7.2f}%")

    print("\n=== OPERATION MIX (overall) ===")
    for op, n in op_count.most_common(15):
        print(f"  {op:<40} {n:>12,}")

    print("\n=== PER-PROCESS OPERATION BREAKDOWN (top 10 processes) ===")
    for name, _ in proc_count.most_common(10):
        print(f"\n[{name or '<empty>'}]")
        for op, n in proc_op[name].most_common(8):
            print(f"  {op:<40} {n:>12,}")

    print("\n=== SAMPLED HOT PATHS (top 5 processes, 1-in-50 sample) ===")
    for name, _ in proc_count.most_common(5):
        print(f"\n[{name or '<empty>'}] top paths:")
        for pth, n in proc_paths[name].most_common(6):
            print(f"  {n:>6}  {pth}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python analyze_csv.py <csv_path> [<csv_path> ...]")
        sys.exit(2)
    analyze(sys.argv[1:])
