"""Data-version manifest for freezing the evaluation protocol (EVALUATION_PROTOCOL.md §2).

Run on the machine that holds the raw data (e.g. the lab PC), NOT in the cloud:
    python research/protocol/make_manifest.py <raw_dir> [<raw_dir> ...] --out data_manifest.csv

Writes one row per file: relative path, size in bytes, SHA-256, modification time (UTC), and a
'kind' guess from the file name (.db / .xdf / _events.csv / _events.json / other).
The manifest contains file names and hashes only, never signal values. File names may contain participant codes
and recording timestamps: keep the manifest with the team's restricted data, commit only if the team agrees.
The SHA-256 of the manifest file itself is printed; record it in EVALUATION_PROTOCOL.md when the protocol is frozen.
"""
import argparse
import csv
import datetime as dt
import hashlib
import os


def sha256(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(chunk), b""):
            h.update(b)
    return h.hexdigest()


def kind(name):
    n = name.lower()
    for suf, k in [("_events.csv", "events_csv"), ("_events.json", "events_json"), (".xdf", "xdf"),
                   (".db-wal", "db_wal"), (".db-shm", "db_shm"), (".db", "db")]:
        if n.endswith(suf):
            return k
    return "other"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--out", default="data_manifest.csv")
    a = ap.parse_args()
    rows = []
    for d in a.dirs:
        d = os.path.abspath(d)
        for root, _, files in os.walk(d):
            for fn in sorted(files):
                p = os.path.join(root, fn)
                st = os.stat(p)
                rows.append(dict(root=os.path.basename(d), rel_path=os.path.relpath(p, d).replace(os.sep, "/"), kind=kind(fn),
                                 size_bytes=st.st_size, sha256=sha256(p),
                                 mtime_utc=dt.datetime.fromtimestamp(st.st_mtime, dt.timezone.utc).isoformat(timespec="seconds")))
    rows.sort(key=lambda r: (r["root"], r["rel_path"]))
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["root", "rel_path", "kind", "size_bytes", "sha256", "mtime_utc"])
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} files -> {a.out}  (manifest sha256 = {sha256(a.out)})")
    for k in sorted({r['kind'] for r in rows}):
        print(f"  {k:12s} {sum(r['kind'] == k for r in rows)}")


if __name__ == "__main__":
    main()
