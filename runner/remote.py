#!/usr/bin/env python3
"""Run TLC jobs on the test runner (a Slurm cluster reached over ssh).

  remote.py sync   AREA [--rev REV]          copy one model area, pinned, to a new run folder
  remote.py submit RUN SCRIPT [--env K=V] [ARGS ...]   sbatch runner/slurm/SCRIPT in that run folder
  remote.py fetch  RUN DEST                  copy the run folder's logs and summaries back

Settings come from config.toml's [runner] table (see config.example.toml):
the ssh target, the root under which run folders are made, and the Slurm
partition and account. None of them is written into this repository.

`sync` takes the files from git at REV (default HEAD), not from the working
tree, and names the run folder <area>-<short sha>, so every run says exactly
which version of the model it checked and an old run folder is never reused
for a newer model. The runner's JDK image and tla2tools.jar are hard-linked
into the folder from [runner] root.
"""
import argparse, io, os, shlex, subprocess, sys, tarfile

try:
    import tomllib
except ImportError:
    sys.exit("remote.py needs Python 3.11 or newer (tomllib)")

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

# What each area's run folder holds: (repository path, folder path) pairs. A
# model and its mutants are copied to the top (tlc-bundle and tlc-resume run
# <module>.tla from RUN_ROOT) and the model again to model/ (the trace
# checkers look for ../model from their own folder).
AREAS = {
    "handshake": [("models/handshake", "."), ("models/handshake/mutants", "."),
                  ("models/handshake", "model"), ("check/handshake", "conformance"),
                  ("runner/slurm", ".")],
    "registration": [("models/registration", "."), ("models/registration/mutants", "."),
                     ("runner/slurm", ".")],
    "sasl": [("models/sasl", "."), ("models/sasl/mutants", "."), ("runner/slurm", ".")],
    "history": [("models/history", "."), ("models/history", "model"),
                ("check/history-catchup", "."), ("harness/history-catchup", "."),
                ("check/history-servers", "servers"), ("harness/history-servers", "servers"),
                ("runner/slurm", ".")],
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
                    if m.isdir() and sub == "." and m.name == "mutants":
                        continue
                    f = t.extractfile(m) if m.isfile() else None
                    m.name = os.path.normpath(os.path.join(sub, m.name))
                    out.addfile(m, f)
    root = r["root"].rstrip("/")
    q = shlex.quote
    # The JDK image and the jar are hard-linked (copied if the link fails), not
    # symlinked: the jobs bind only RUN_ROOT into the container, so a symlink
    # to the root would dangle inside it.
    links = "".join(f"ln {q(root + '/' + src)} {q(dest + '/' + name)} 2>/dev/null || "
                    f"cp {q(root + '/' + src)} {q(dest + '/' + name)}; "
                    for src, name in ((r.get("image", "temurin21.sif"), "temurin21.sif"),
                                      (r.get("tla_jar", "tla2tools.jar"), "tla2tools.jar")))
    script = (f"set -e; test ! -e {q(dest)} || {{ echo {q(dest)} exists; exit 1; }}; mkdir -p {q(dest)}; "
              f"tar -x -C {q(dest)}; {links}"
              f"echo {q(a.rev)} {q(sha)} > {q(dest + '/REVISION')}")
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
    env = ["ALL", f"RUN_ROOT={dest}"] + a.env   # e.g. --env TLC_MODULE=RefSafety_e10
    argv = [*flags, "--export=" + ",".join(env), a.script, *a.args]
    q = shlex.quote
    ssh(r, f"cd {q(dest)} && RUN_ROOT={q(dest)} sbatch " + " ".join(q(x) for x in argv))


def fetch(a):
    r = cfg()
    dest = f"{r['root'].rstrip('/')}/{a.run}"
    os.makedirs(a.dest, exist_ok=True)
    tar = subprocess.run(["ssh", r["ssh"],
                          f"cd {shlex.quote(dest)} && tar -c --exclude='states*' --exclude='*.sif' --exclude='*.jar' ."],
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
    s.add_argument("--env", action="append", default=[], metavar="K=V",
                   help="extra variable for the job (TLC_MODULE, TLC_EXTRA, ...); repeatable")
    s.add_argument("args", nargs="*"); s.set_defaults(fn=submit)
    s = sub.add_parser("fetch"); s.add_argument("run"); s.add_argument("dest"); s.set_defaults(fn=fetch)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
