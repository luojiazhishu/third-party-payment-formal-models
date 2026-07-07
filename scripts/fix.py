import re
import sys
from pathlib import Path

RULE_LINE_RE = re.compile(r'^\s*rule\b.*?:\s*(//.*)?$', re.UNICODE)
ROLE_IN_BRACKETS_RE = re.compile(r'(\brole\s*=\s*)(?!")([A-Za-z_][A-Za-z0-9_\-]*)')
BRACKET_BLOCK_RE = re.compile(r'\[[^\]]*\]')

def fix_rule_line(line: str) -> str:
    if not RULE_LINE_RE.match(line):
        return line

    m = BRACKET_BLOCK_RE.search(line)
    if not m:
        return line

    block = m.group(0)
    new_block = ROLE_IN_BRACKETS_RE.sub(r'\1"\2"', block)
    if new_block == block:
        return line

    return line[:m.start()] + new_block + line[m.end():]

def fix_file(p: Path) -> int:
    text = p.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines(True)  # keep line endings
    new_lines = [fix_rule_line(ln) for ln in lines]
    new_text = "".join(new_lines)

    if new_text == text:
        return 0

    p.write_text(new_text, encoding="utf-8", errors="replace")
    return 1

def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <file-or-dir>", file=sys.stderr)
        sys.exit(2)

    target = Path(sys.argv[1]).resolve()
    if not target.exists():
        print(f"[ERROR] not found: {target}", file=sys.stderr)
        sys.exit(2)

    if target.is_file():
        files = [target]
    else:
        files = sorted(target.rglob("*.spthy"))

    modified = 0
    for f in files:
        try:
            modified += fix_file(f)
        except Exception as e:
            print(f"[WARN] failed on {f}: {e}", file=sys.stderr)

    print(f"[DONE] processed={len(files)}, modified={modified}")

if __name__ == "__main__":
    main()
