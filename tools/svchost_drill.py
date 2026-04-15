"""Drill-down analyzer for noisy svchost.exe in a Procmon CSV.

Usage:
    python svchost_drill.py <csv_path> [<csv_path> ...]

For each svchost.exe PID seen in the log, prints:
  * Operation counts (total FS + WriteFile specifically)
  * Top 3 PIDs by WriteFile: operation mix, WriteFile target paths, hot paths

Map a noisy PID to its service by running:
    tasklist /SVC /FI "PID eq <PID>"
(while the PID is still alive).
"""

import csv
import sys
import time
from collections import Counter, defaultdict


def drill(paths):
    pid_op = defaultdict(Counter)
    pid_write_paths = defaultdict(Counter)
    pid_any_paths = defaultdict(Counter)
    total = 0
    svc_rows = 0
    t0 = time.time()

    for path in paths:
        print(f"Reading {path}...", flush=True)
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f)
            next(reader)
            for row in reader:
                total += 1
                if len(row) < 5:
                    continue
                if row[1] != "svchost.exe":
                    continue
                svc_rows += 1
                pid = row[2]
                op = row[3]
                p = row[4]
                pid_op[pid][op] += 1
                if op == "WriteFile" and p:
                    pid_write_paths[pid][p[:160]] += 1
                if svc_rows % 25 == 0 and p:
                    pid_any_paths[pid][p[:160]] += 1

    dt = time.time() - t0
    print(f"Rows: {total:,}   svchost rows: {svc_rows:,}   time: {dt:.0f}s\n")

    print("=== svchost.exe PIDs ranked by WriteFile count ===")
    writers = [
        (pid, ops.get("WriteFile", 0), sum(ops.values())) for pid, ops in pid_op.items()
    ]
    writers.sort(key=lambda x: -x[1])
    print(f"{'PID':>8} {'WriteFile':>10} {'Total FS':>10}")
    for pid, wf, tot in writers[:15]:
        print(f"{pid:>8} {wf:>10,} {tot:>10,}")

    print("\n=== Operation mix per top-3 svchost PIDs ===")
    for pid, _, _ in writers[:3]:
        print(f"\n[svchost PID {pid}]")
        for op, n in pid_op[pid].most_common(10):
            print(f"  {op:<40} {n:>10,}")

    print("\n=== WriteFile target paths per top-3 svchost PIDs ===")
    for pid, wf, _ in writers[:3]:
        if wf == 0:
            continue
        print(f"\n[PID {pid}] WriteFile targets:")
        for pth, n in pid_write_paths[pid].most_common(15):
            print(f"  {n:>7,}  {pth}")

    print("\n=== All-operation hot paths per top-3 svchost PIDs (1-in-25 sample) ===")
    for pid, _, _ in writers[:3]:
        print(f"\n[PID {pid}] hot paths:")
        for pth, n in pid_any_paths[pid].most_common(10):
            print(f"  {n:>6}  {pth}")

    print("\nTo map PID to service (while the PID is still running):")
    for pid, _, _ in writers[:3]:
        print(f'  tasklist /SVC /FI "PID eq {pid}"')


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python svchost_drill.py <csv_path> [<csv_path> ...]")
        sys.exit(2)
    drill(sys.argv[1:])
