#!/usr/bin/env python3
"""Run TLC jobs on the test runner (a Slurm cluster reached over ssh).

  remote.py sync   AREA [--rev REV]          copy one model area, pinned, to a new run folder
  remote.py submit RUN SCRIPT [ARGS ...]     sbatch runner/slurm/SCRIPT in that run folder
  remote.py fetch  RUN DEST                  copy the run folder's logs and summaries back

Settings come from config.toml's [runner] table (see config.example.toml):
the ssh target, the root under which run folders are made, and the Slurm
partition and account. None of them is written into this repository.

`sync` takes the files from git at REV (default HEAD), not from the working
tree, and names the run folder <area>-<short sha>, so every run says exactly
which version of the model it checked and an old run folder is never reused
for a newer model. The runner's JDK image and tla2tools.jar are linked into
the folder from [runner] root.
"""
import argparse, io, os, subprocess, sys, tarfile

try:
    import tomllib
except ImportError:
    sys.exit("remote.py needs Python 3.11 or newer (tomllib)")

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

# What each area's run folder holds: (repository path, folder path) pairs. A
# model is copied both to the top (tlc-bundle, tlc-resume) and to model/ (the
# trace checkers, which look for ../model from their own folder).
AREAS = {
    "handshake": [("models/handshake", "."), ("models/handshake", "model"),
                  ("check/handshake", "conformance"), ("runner/slurm", ".")],
    "registration": [("models/registration", "."), ("runner/slurm", ".")],
    "sasl": [("models/sasl", "."), ("runner/slurm", ".")],
    "history": [("models/history", "."), ("models/history", "model"),
                ("check/history-catchup", "."), ("check/history-servers", "servers"),
                ("harness/history-servers", "servers"), ("runner/slurm", ".")],
}


def cfg():
    path = os.path.join(REPO, "config.toml")
    if not os.path.exists(path):
        sys.exit("no config.toml: copy config.example.toml and fill in [runner]")
    r = tomllib.load(open(path, "rb")).get("runner")
    if not r or not r.get("ssh") or not r.get("root"):
        sys.exit("config.toml needs [runner] ssh and root")
    return r


def git(*args):
    return subprocess.check_output(["git", "-C", REPO, *args])


def ssh(r, command, stdin=None):
    return subprocess.run(["ssh", r["ssh"], command], input=stdin, check=True)


def sync(a):
    r = cfg()
    if a.area not in AREAS:
        sys.exit(f"unknown area {a.area}; one of {', '.join(AREAS)}")
    sha = git("rev-parse", "--short=10", a.rev).decode().strip()
    run = f"{a.area}-{sha}"
    dest = f"{r['root'].rstrip('/')}/{run}"
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as out:
        for src, sub in AREAS[a.area]:
            raw = git("archive", "--format=tar", f"{a.rev}:{src}")
            with tarfile.open(fileobj=io.BytesIO(raw)) as t:
                for m in t.getmembers():
                    f = t.extractfile(m) if m.isfile() else None
                    m.name = os.path.normpath(os.path.join(sub, m.name))
                    out.addfile(m, f)
    root = r["root"].rstrip("/")
    script = (f"set -e; test ! -e {dest} || {{ echo {dest} exists; exit 1; }}; mkdir -p {dest}; "
              f"tar -x -C {dest}; ln -s {root}/{r.get('image', 'temurin21.sif')} {dest}/temurin21.sif; "
              f"ln -s {root}/{r.get('tla_jar', 'tla2tools.jar')} {dest}/tla2tools.jar; "
              f"echo {a.rev} {sha} > {dest}/REVISION")
    ssh(r, script, stdin=buf.getvalue())
    print(run)


def submit(a):
    r = cfg()
    dest = f"{r['root'].rstrip('/')}/{a.run}"
    flags = []
    if r.get("partition"):
        flags += ["-p", r["partition"]]
    if r.get("account"):
        flags += ["-A", r["account"]]
    args = " ".join([*flags, f"--export=ALL,RUN_ROOT={dest}", a.script, *a.args])
    ssh(r, f"cd {dest} && RUN_ROOT={dest} sbatch {args}")


def fetch(a):
    r = cfg()
    dest = f"{r['root'].rstrip('/')}/{a.run}"
    os.makedirs(a.dest, exist_ok=True)
    tar = subprocess.run(["ssh", r["ssh"],
                          f"cd {dest} && tar -c --exclude='states*' --exclude='*.sif' --exclude='*.jar' ."],
                         check=True, capture_output=True).stdout
    with tarfile.open(fileobj=io.BytesIO(tar)) as t:
        t.extractall(a.dest, filter="data")
    print(a.dest)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sync"); s.add_argument("area"); s.add_argument("--rev", default="HEAD")
    s.set_defaults(fn=sync)
    s = sub.add_parser("submit"); s.add_argument("run"); s.add_argument("script")
    s.add_argument("args", nargs="*"); s.set_defaults(fn=submit)
    s = sub.add_parser("fetch"); s.add_argument("run"); s.add_argument("dest"); s.set_defaults(fn=fetch)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
