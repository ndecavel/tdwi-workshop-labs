#!/usr/bin/env python3
"""Move a pinned asset reference everywhere it appears. Never do this by hand.

What is pinned, and where:
  notebooks  https://raw.githubusercontent.com/ndecavel/tdwi-workshop-labs/<sha>/...
             in Labs/*.ipynb (the config and the source documents; 9 places in 6 notebooks)
  golden     the same kind of URL for the golden CSVs, inside data/dataset_config.json
             (2 places)
  release    .../releases/download/<tag>/... in the config and notebooks (the parsed
             corpus parquet files)

Usage:
  python tools/set_pin.py notebooks <sha> [--dry-run]
  python tools/set_pin.py golden <sha> [--dry-run]
  python tools/set_pin.py release <tag> [--dry-run]

Commit pins accept a short or full sha and are resolved with `git rev-parse`; the commit
must exist locally. Every pinned path must exist at that commit (`git cat-file -e`),
otherwise nothing is written. A warning is printed when no remote branch contains the
commit, because raw.githubusercontent.com can only serve pushed commits.

Text is replaced in place, so the JSON formatting stays byte-exact.

THE TWO-COMMIT RULE. A commit cannot contain its own hash. So moving a pin is always:
  1. one commit with the asset change (new config, new documents, new golden CSV), pushed;
  2. then run this tool and make a second commit that points the notebooks at the first.
Never point a pin at the commit you are about to make.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "data" / "dataset_config.json"
REPO = "ndecavel/tdwi-workshop-labs"
# group 1: prefix, group 2: sha, group 3: path (stops at a quote, backslash, space, brace or paren)
RAW_RE = re.compile(r"(https://raw\.githubusercontent\.com/" + re.escape(REPO) + r"/)([0-9a-f]{40})/([^\s\"'\\{}()<>]*)")
REL_RE = re.compile(r"(releases/download/)([A-Za-z0-9._-]+)(/)")


def git(*args, check=True):
    r = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True)
    if check and r.returncode != 0:
        sys.exit(f"git {' '.join(args)} failed: {r.stderr.strip()}")
    return r


def notebooks():
    return sorted((ROOT / "Labs").glob("*.ipynb"))


def locate(path, text, regex, accept=lambda m: True):
    """Yield (match, label) for each hit. Label is 'cell N' for notebooks, 'line N' otherwise."""
    if path.suffix == ".ipynb":
        # A hit's cell is found by counting cells whose source contains the matched text.
        cells = json.loads(text)["cells"]
        for i, c in enumerate(cells):
            src = c["source"] if isinstance(c["source"], str) else "".join(c["source"])
            for m in regex.finditer(src):
                if accept(m):
                    yield m, f"cell {i}"
    else:
        for n, line in enumerate(text.splitlines(), 1):
            for m in regex.finditer(line):
                if accept(m):
                    yield m, f"line {n}"


def rewrite(path, regex, repl, accept, dry, report):
    text = path.read_text(encoding="utf-8")
    hits = list(locate(path, text, regex, accept))
    for m, label in hits:
        report.append((path.name, label, m))
    # Substitute in the raw text; it must find the same number of hits as the cell scan.
    count = [0]

    def sub(m):
        if not accept(m):
            return m.group(0)
        count[0] += 1
        return repl(m)

    new = regex.sub(sub, text)
    if count[0] != len(hits):
        sys.exit(f"{path.name}: found {len(hits)} pins by cell but {count[0]} in the file text; refusing")
    if new != text and not dry:
        path.write_text(new, encoding="utf-8")
    return len(hits)


def resolve(sha):
    r = git("rev-parse", "--verify", "--quiet", f"{sha}^{{commit}}", check=False)
    full = r.stdout.strip()
    if r.returncode != 0 or not re.fullmatch(r"[0-9a-f]{40}", full):
        sys.exit(f"'{sha}' is not a commit in this repository. Fetch it first.")
    return full


def verify_commit(full, paths):
    missing = []
    for p in sorted(paths):
        if git("cat-file", "-e", f"{full}:{p.rstrip('/')}", check=False).returncode != 0:
            missing.append(p)
    if missing:
        sys.exit(f"Refusing: not present at {full[:12]}: " + ", ".join(missing))
    out = git("branch", "-r", "--contains", full, check=False).stdout.strip()
    if not out:
        print(f"WARNING: no remote branch contains {full[:12]}. raw.githubusercontent.com "
              "cannot serve it until it is pushed.")


def set_commit(files, sha, accept, dry):
    full = resolve(sha)
    # First pass: collect paths, write nothing.
    report = []
    for f in files:
        rewrite(f, RAW_RE, lambda m: m.group(0), accept, True, report)
    verify_commit(full, {m.group(3) for _, _, m in report if m.group(3)})
    report = []
    for f in files:
        rewrite(f, RAW_RE, lambda m: f"{m.group(1)}{full}/{m.group(3)}", accept, dry, report)
    for name, label, m in report:
        print(f"{name}, {label}: {m.group(2)[:12]} -> {full[:12]}  ({m.group(3) or '/'})")
    files_hit = len({n for n, _, _ in report})
    print(f"{'Would replace' if dry else 'Replaced'} {len(report)} pin(s) in {files_hit} file(s).")


def set_release(tag, dry):
    if not re.fullmatch(r"[A-Za-z0-9._-]+", tag):
        sys.exit(f"'{tag}' is not a valid tag name.")
    if not git("tag", "-l", tag, check=False).stdout.strip():
        print(f"NOTE: tag '{tag}' is not a local git tag; make sure the release exists on GitHub.")
    report = []
    for f in [CONFIG, *notebooks()]:
        rewrite(f, REL_RE, lambda m: f"{m.group(1)}{tag}{m.group(3)}", lambda m: True, dry, report)
    for name, label, m in report:
        print(f"{name}, {label}: {m.group(2)} -> {tag}")
    print(f"{'Would replace' if dry else 'Replaced'} {len(report)} release pin(s) in "
          f"{len({n for n, _, _ in report})} file(s).")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("what", choices=["notebooks", "golden", "release"])
    ap.add_argument("value", help="commit sha (short or full) or release tag")
    ap.add_argument("--dry-run", action="store_true", help="print replacements, write nothing")
    a = ap.parse_args()
    if a.what == "notebooks":
        set_commit(notebooks(), a.value, lambda m: True, a.dry_run)
    elif a.what == "golden":
        set_commit([CONFIG], a.value, lambda m: "Golden_Test" in m.group(3), a.dry_run)
    else:
        set_release(a.value, a.dry_run)


if __name__ == "__main__":
    main()
