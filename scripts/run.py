import argparse
import os
import shutil
import subprocess
import sys
import time
from collections import deque
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from datetime import datetime
import threading


MEM_POLL_INTERVAL = 0.2

# Number of RTS threads per tamarin process (passed as +RTS -N<...>).
RTS_THREADS = 4


def extract_final_block(stdout_tail: str) -> str:
    SEP = "=============================================================================="
    KEY = "summary of summaries:"

    if not stdout_tail:
        return ""

    kpos = stdout_tail.rfind(KEY)
    if kpos == -1:
        return ""

    start = stdout_tail.rfind(SEP, 0, kpos)
    if start == -1:
        start = kpos

    end_sep = stdout_tail.find(SEP, kpos)
    if end_sep == -1:
        return stdout_tail[start:].strip("\n")

    nl = stdout_tail.find("\n", end_sep)
    if nl == -1:
        nl = len(stdout_tail)
    else:
        nl += 1

    return stdout_tail[start:nl].strip("\n")


def append_block(out_file: Path, block: str) -> None:
    if not block:
        return
    out_file.parent.mkdir(parents=True, exist_ok=True)
    if not out_file.exists():
        out_file.write_text("", encoding="utf-8", errors="replace")

    with out_file.open("a", encoding="utf-8", errors="replace") as f:
        f.write("\n")
        f.write(block.rstrip("\n"))
        f.write("\n")


def fmt_sec(sec: float) -> str:
    if sec < 60:
        return f"{sec:.2f}s"
    m, s = divmod(int(sec), 60)
    if m < 60:
        return f"{m:d}:{s:02d}"
    h, m = divmod(m, 60)
    return f"{h:d}:{m:02d}:{s:02d}"


def fmt_kb(kb: int) -> str:
    if kb <= 0:
        return "N/A"
    mb = kb / 1024.0
    if mb < 1024:
        return f"{mb:.1f}MB"
    gb = mb / 1024.0
    return f"{gb:.2f}GB"


def _read_proc_status_kb(pid: int, key: str) -> int:
    """
    Read a value like 'VmHWM:' from /proc/<pid>/status (unit: kB).
    Return 0 on failure.
    """
    try:
        with open(f"/proc/{pid}/status", "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.startswith(key):
                    # e.g. "VmHWM:\t  123456 kB"
                    parts = line.split()
                    for p in parts:
                        if p.isdigit():
                            return int(p)
        return 0
    except Exception:
        return 0


def run_one(tamarin_bin: str, spthy_path: str, out_dir: str, log_dir: str, rel_path_str: str, rts_threads: int):
    spthy = Path(spthy_path)
    out_root = Path(out_dir)
    log_root = Path(log_dir)
    rel_path = Path(rel_path_str)  # Path relative to spthy_dir, e.g., base/a.spthy

    # Model name: by default use the first segment of rel_path (base/ms/ps)
    model = rel_path.parts[0] if len(rel_path.parts) >= 2 else "root"

    # Output file: results/<rel_path>
    out_file = out_root / rel_path
    out_file.parent.mkdir(parents=True, exist_ok=True)

    # Log file: log/<rel_path>.log (same directory structure)
    log_file = (log_root / rel_path).with_suffix(".log")
    log_file.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        tamarin_bin,
        "--prove",
        f"--output={out_file}",
        str(spthy),
        "+RTS",
        f"-N{max(1, int(rts_threads))}",
        "-RTS",
        "--derivcheck-timeout=0"
    ]

    t0 = time.perf_counter()
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True,
    )

    tail = deque(maxlen=6000)

    # Monitor peak memory usage (VmHWM) of the child process
    peak_kb = 0
    stop_evt = threading.Event()

    def mem_monitor():
        nonlocal peak_kb
        if proc.pid is None:
            return
        while not stop_evt.is_set():
            v = _read_proc_status_kb(proc.pid, "VmHWM:")  # Peak RSS
            if v > peak_kb:
                peak_kb = v
            if proc.poll() is not None:
                break
            time.sleep(MEM_POLL_INTERVAL)

    th = threading.Thread(target=mem_monitor, daemon=True)
    th.start()

    # Create/truncate the log file first so it shows up immediately
    with log_file.open("w", encoding="utf-8", errors="replace") as lf:
        lf.flush()
        if proc.stdout is not None:
            for line in proc.stdout:
                tail.append(line)
                lf.write(line)
                lf.flush()

    rc = proc.wait()
    dur = time.perf_counter() - t0

    stop_evt.set()
    th.join(timeout=1.0)

    # Extract the summary block from the tail output and append it to the output file
    stdout_tail = "".join(tail)
    block = extract_final_block(stdout_tail)
    append_block(out_file, block)

    return {
        "file": str(spthy),
        "out": str(out_file),
        "log": str(log_file),
        "rc": int(rc),
        "sec": dur,
        "peak_kb": int(peak_kb),
        "model": model,
    }


def main():
    ap = argparse.ArgumentParser(description="Parallel tamarin runner (recursive, stream logs, append summary block, peak memory).")
    ap.add_argument("-d", dest="spthy_dir", help="Root directory containing .spthy files (recursive). e.g. models/")
    ap.add_argument("-j", dest="jobs", type=int, help="Number of parallel processes.")
    ap.add_argument("-o", dest="out_dir", help="Output root directory, e.g. results")
    ap.add_argument("-log", dest="log_dir", default="log", help="Log root directory (default: log)")
    args = ap.parse_args()

    run_log = Path("run.log")

    with run_log.open("w", encoding="utf-8", errors="replace") as rf:
        def log_print(*a, sep=" ", end="\n"):
            msg = sep.join(str(x) for x in a)
            print(msg, end=end, flush=True)
            rf.write(msg + end)
            rf.flush()

        # Overall timing
        global_t0 = time.perf_counter()
        start_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        spthy_dir = Path(args.spthy_dir).resolve()
        out_dir = Path(args.out_dir).resolve()
        log_dir = Path(args.log_dir).resolve()
        jobs = int(args.jobs)

        if jobs < 1:
            log_print("[ERROR] jobs must be >= 1")
            sys.exit(2)
        if not spthy_dir.is_dir():
            log_print(f"[ERROR] not a directory: {spthy_dir}")
            sys.exit(2)

        tamarin_bin = shutil.which("tamarin-prover")
        if not tamarin_bin:
            log_print("[ERROR] tamarin-prover not found in PATH")
            sys.exit(127)

        # Recursively scan subdirectories
        files = sorted(spthy_dir.rglob("*.spthy"))
        if not files:
            log_print(f"[WARN] no .spthy found under {spthy_dir} (recursive)")
            return

        out_dir.mkdir(parents=True, exist_ok=True)
        log_dir.mkdir(parents=True, exist_ok=True)

        rts_threads = RTS_THREADS

        log_print(f"[INFO] start time = {start_ts}")
        log_print(f"[INFO] found {len(files)} .spthy files (recursive)")
        log_print(f"[INFO] jobs={jobs}, RTS threads/process={rts_threads}")
        log_print(f"[INFO] input(root)={spthy_dir}")
        log_print(f"[INFO] output root={out_dir}")
        log_print(f"[INFO] log root={log_dir}")
        log_print(f"[INFO] run log={run_log.resolve()}\n")

        ok = 0
        fail = 0
        secs = []

        # Summary: peak memory (kB) per model
        model_peak_kb = {}
        overall_peak_kb = 0

        with ProcessPoolExecutor(max_workers=jobs) as ex:
            futs = []
            for f in files:
                rel_path = f.relative_to(spthy_dir)  # Preserve subdir structure: base/... ms/... ps/...
                futs.append(ex.submit(
                    run_one,
                    tamarin_bin,
                    str(f),
                    str(out_dir),
                    str(log_dir),
                    str(rel_path),
                    rts_threads,
                ))

            for i, fut in enumerate(as_completed(futs), 1):
                try:
                    r = fut.result()
                except Exception as e:
                    fail += 1
                    log_print(f"[{i:>3}/{len(files)}] FAIL (exception) {e!r}")
                    continue

                secs.append(float(r["sec"]))
                name = Path(r["file"]).name
                mem_kb = int(r.get("peak_kb", 0))
                model = r.get("model", "unknown")

                if mem_kb > overall_peak_kb:
                    overall_peak_kb = mem_kb
                if mem_kb > model_peak_kb.get(model, 0):
                    model_peak_kb[model] = mem_kb

                if r["rc"] == 0:
                    ok += 1
                    log_print(f"[{i:>3}/{len(files)}] OK   {fmt_sec(r['sec'])}  mem_peak={fmt_kb(mem_kb)}  {name}")
                else:
                    fail += 1
                    log_print(f"[{i:>3}/{len(files)}] FAIL rc={r['rc']} {fmt_sec(r['sec'])}  mem_peak={fmt_kb(mem_kb)}  {name}")

                log_print(f"            model: {model}")
                log_print(f"            out:   {r['out']}")
                log_print(f"            log:   {r['log']}")

        total_wall = time.perf_counter() - global_t0
        end_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        n = len(secs)
        avg = (sum(secs) / n) if n else 0.0
        fastest = min(secs) if n else 0.0
        slowest = max(secs) if n else 0.0
        throughput = (n / total_wall * 60.0) if total_wall > 1e-9 else 0.0

        log_print("\n==== SUMMARY ====")
        log_print(f"OK={ok}, FAIL={fail}")
        log_print(f"[INFO] end time   = {end_ts}")
        log_print(f"[INFO] total wall = {fmt_sec(total_wall)}")
        log_print(f"[INFO] per-file   = avg {fmt_sec(avg)} | min {fmt_sec(fastest)} | max {fmt_sec(slowest)}")
        log_print(f"[INFO] throughput = {throughput:.2f} files/min")

        log_print("\n==== PEAK MEMORY BY MODEL (VmHWM) ====")
        for m in sorted(model_peak_kb.keys()):
            log_print(f"{m:<16} {fmt_kb(model_peak_kb[m])}")
        log_print(f"{'OVERALL':<16} {fmt_kb(overall_peak_kb)}")

        sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
