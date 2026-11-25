"""Data-version manifest for freezing the evaluation protocol (EVALUATION_PROTOCOL.md §2).

Run on the machine that holds the raw data (e.g. the lab PC), NOT in the cloud:
    python research/protocol/make_manifest.py <raw_dir> [<raw_dir> ...] --out data_manifest.csv

Writes one row per file: relative path, size in bytes, SHA-256, modification time (UTC), and a
'kind' guess from the file name (.db / .xdf / _events.csv / _events.json / other).
The manifest contains file paths, kinds, sizes, hashes and modification times, never signal values. File names may
contain participant codes and recording timestamps: keep the manifest with the team's restricted data, commit only if
the team agrees.
DATA VERSION: the printed `data_version_sha256` is computed ONLY from the sorted (root, rel_path, size_bytes, sha256)
of the data files, excluding mtime (copies/restores keep the same version) and excluding SQLite side files
(-wal / -shm), which change whenever a database is opened. Checkpoint or close the databases before running if -wal
files exist (they are listed with a warning). Record data_version_sha256 in EVALUATION_PROTOCOL.md §2 at freeze.
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
    core = [r for r in rows if r["kind"] not in ("db_wal", "db_shm")]
    h = hashlib.sha256()
    for r in core:
        h.update(f"{r['root']}\t{r['rel_path']}\t{r['size_bytes']}\t{r['sha256']}\n".encode("utf-8"))
    print(f"{len(rows)} files -> {a.out}")
    print(f"data_version_sha256 = {h.hexdigest()}  (over {len(core)} files; mtime and -wal/-shm excluded)")
    side = [r["rel_path"] for r in rows if r["kind"] in ("db_wal", "db_shm")]
    if side:
        print(f"WARNING: {len(side)} SQLite side files present (not in data version); checkpoint/close databases first: {side[:5]}")
    for k in sorted({r['kind'] for r in rows}):
        print(f"  {k:12s} {sum(r['kind'] == k for r in rows)}")


if __name__ == "__main__":
    main()
