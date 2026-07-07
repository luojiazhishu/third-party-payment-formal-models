import os
import re
import csv
import json
import argparse
from pathlib import Path


def parse_lemma_results(text: str):
    lemmas = []
    pattern = r'(.+?) \((.+?)\): (.+?) \((.+?) steps\)'
    matches = re.findall(pattern, text)
    for m in matches:
        lemmas.append({
            "name": m[0].strip(),
            "type": m[1].strip(),
            "result": m[2].strip(),
            "steps": m[3].strip(),
        })
    return lemmas


def parse_time_info(text: str) -> str:
    # Return "" instead of crashing when 'processing time:' is absent.
    m = re.findall(r'processing time: (.+)', text)
    return m[0].strip() if m else ""


def parse_one_file(path: Path) -> dict:
    """Parse a single .spthy result file into {time, lemmas}."""
    with path.open("r", encoding="utf-8", errors="replace") as fp:
        data = fp.read()
    # Same domain-specific slice as before: content after the last 'end\n'.
    data = data.split("end\n")[-1]
    return {
        "time": parse_time_info(data),
        "lemmas": parse_lemma_results(data),
    }


def parse_dir(d: Path) -> dict:
    """Parse all .spthy files directly inside directory `d` (non-recursive).
    Returns { "<filename>.spthy": {time, lemmas}, ... }."""
    out = {}
    for name in sorted(os.listdir(d)):
        f = d / name
        if f.is_file() and f.name.endswith(".spthy"):
            out[name] = parse_one_file(f)
    return out


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", errors="replace") as fp:
        json.dump(obj, fp, ensure_ascii=False, indent=4)


def rows_from_dir_data(dir_label: str, dir_data: dict):
    """Flatten one directory's data into CSV rows.
    dir_label is the directory's path relative to the scan root
    (used as the 'model' column so cross-dir same-name files stay distinct)."""
    rows = []
    for case, info in dir_data.items():
        t = info.get("time", "")
        lemmas = info.get("lemmas", []) or []
        if not lemmas:
            rows.append([dir_label, case, t, "", "", "", ""])
            continue
        for l in lemmas:
            rows.append([
                dir_label, case, t,
                l.get("name", ""), l.get("type", ""),
                l.get("result", ""), l.get("steps", ""),
            ])
    return rows


def write_csv(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    headers = ['model', 'case', 'time', 'lemma', 'type', 'result', 'steps']
    with path.open("w", encoding="utf-8", errors="replace", newline="") as cf:
        writer = csv.writer(cf)
        writer.writerow(headers)
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description="Process model verification results (recursive).")
    parser.add_argument("-r", "--result", dest="result_dir",
                        help="Result ROOT directory. Recurses into all subdirs.")
    parser.add_argument('--csv', dest='csv', action='store_true',
                        help="Also write per-dir result.csv and an aggregate results.csv at the root.")
    args = parser.parse_args()

    # Same fallback as before: no -r given -> latest dir starting with 'result'.
    if not args.result_dir:
        cands = [d for d in os.listdir() if os.path.isdir(d) and d.startswith("result")]
        if not cands:
            print("[ERROR] no result directory found", flush=True)
            raise SystemExit(-1)
        result_dir = sorted(cands)[-1]
    else:
        result_dir = args.result_dir

    root = Path(result_dir).resolve()
    if not root.is_dir():
        print(f"[ERROR] not a directory: {root}", flush=True)
        raise SystemExit(-1)

    # Find every directory (root included) that directly contains .spthy files.
    dirs_with_spthy = []
    for cur, _subdirs, files in os.walk(root):
        if any(name.endswith(".spthy") for name in files):
            dirs_with_spthy.append(Path(cur))
    dirs_with_spthy.sort()

    if not dirs_with_spthy:
        print(f"[WARN] no .spthy files found under {root} (recursive)", flush=True)
        # Still emit an empty aggregate so downstream steps have a stable file.
        write_json(root / "results.json", {})
        return

    aggregate = {}          # { "<reldir>": { "<file>.spthy": {time, lemmas} } }
    all_rows = []           # combined CSV rows across every directory

    for d in dirs_with_spthy:
        dir_data = parse_dir(d)
        if not dir_data:
            continue

        rel = d.relative_to(root)
        dir_label = "." if str(rel) == "." else str(rel)

        # 1) per-directory summary (unchanged behavior, singular name)
        write_json(d / "result.json", dir_data)

        # 2) feed the aggregate, keyed by directory to avoid name collisions
        aggregate[dir_label] = dir_data

        rows = rows_from_dir_data(dir_label, dir_data)
        all_rows.extend(rows)

        if args.csv:
            write_csv(d / "result.csv", rows)

        print(f"  [PARSE] {dir_label}: {len(dir_data)} file(s) -> {d / 'result.json'}", flush=True)

    # 3) one combined results.json at the root (plural name, as requested)
    agg_path = root / "results.json"
    write_json(agg_path, aggregate)
    print(f"[SUMMARY] aggregate JSON written to: {agg_path}", flush=True)

    if args.csv:
        agg_csv = root / "results.csv"
        write_csv(agg_csv, all_rows)
        print(f"[SUMMARY] aggregate CSV written to:  {agg_csv}", flush=True)


if __name__ == "__main__":
    main()
