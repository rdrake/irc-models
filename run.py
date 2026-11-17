#!/usr/bin/env python3
"""Record and check one suite against one server named in config.toml.

  run.py record SUITE --server NAME --out DIR [-- EXTRA RECORDER FLAGS]
  run.py check  SUITE --in DIR [--tlc] [-- EXTRA CHECKER FLAGS]

SUITE is one of: handshake, registration, sasl, history-servers,
labeled-response. `record` writes DIR/<suite>.jsonl; `check` writes
DIR/<suite>/ in the layout compare.py reads. The recorders and checkers can
also be run by hand: this only turns the config into their flags.
"""
import argparse, os, shlex, subprocess, sys

try:
    import tomllib
except ImportError:  # Python < 3.11
    sys.exit("run.py needs Python 3.11 or newer (tomllib)")

HERE = os.path.dirname(os.path.abspath(__file__))


def recorder_argv(suite, s, out):
    py = [sys.executable]
    host, port = s["host"], str(s["port"])
    label = ["--server-label", s.get("label", "")]
    acc = s.get("accounts", [])
    if s.get("tls") and suite != "history-servers":
        sys.exit(f"{suite}: its recorder speaks plain TCP only; point it at a plaintext port (tls = false)")
    if suite == "handshake":
        argv = py + [f"{HERE}/harness/handshake/drive.py", host, port, out,
                     "--settle", str(s.get("settle", 0.5))]
        if s.get("backend_down") and s.get("backend_up"):
            argv += ["--svc-down", s["backend_down"], "--svc-up", s["backend_up"]]
        return argv
    if suite == "registration":
        argv = py + [f"{HERE}/harness/registration/record_reg.py", host, port, out] + label
        return argv + (["--pass", s["password"]] if s.get("password") else [])
    if suite == "sasl":
        if len(acc) < 2:
            sys.exit("sasl needs two accounts in the server's config")
        argv = py + [f"{HERE}/harness/sasl/record_sasl.py", host, port, out] + label + \
            ["--acct1", acc[0], "--acct2", acc[1]]
        if s.get("backend_down") and s.get("backend_up"):
            argv += ["--hook-cmd-down", s["backend_down"], "--hook-cmd-up", s["backend_up"]]
        return argv
    if suite == "history-servers":
        argv = py + [f"{HERE}/harness/history-servers/drive.py", host, port, out] + label
        if s.get("tls"):
            argv.append("--tls")
        if s.get("password"):
            argv += ["--pass", s["password"]]
        for role in s.get("history_sasl", []):        # "q=account:password"
            argv += ["--sasl", role]
        return argv
    if suite == "labeled-response":
        return py + [f"{HERE}/harness/labeled-response/record_lr.py", host, port, out] + label
    sys.exit(f"unknown suite {suite}")


def checker_argv(suite, trace, out_dir, tlc):
    py = [sys.executable]
    if suite == "handshake":
        return py + [f"{HERE}/check/handshake/check.py", trace, out_dir]
    if suite == "registration":
        return py + [f"{HERE}/check/registration/check.py", trace, "--json", f"{out_dir}/check.json"]
    if suite == "sasl":
        return py + [f"{HERE}/check/sasl/summarize.py", trace, "--json", f"{out_dir}/summary.json"]
    if suite == "history-servers":
        argv = py + [f"{HERE}/check/history-servers/check.py", trace, "--json", f"{out_dir}/check.json"]
        return argv + (["--tlc", f"{out_dir}/tlc"] if tlc else [])
    if suite == "labeled-response":
        return py + [f"{HERE}/check/labeled-response/check_lr.py", trace]
    sys.exit(f"unknown suite {suite}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["record", "check"])
    ap.add_argument("suite")
    ap.add_argument("--server")
    ap.add_argument("--out")
    ap.add_argument("--in", dest="indir")
    ap.add_argument("--tlc", action="store_true", help="also run the TLC trace check, where the checker has one")
    ap.add_argument("--config", default=os.path.join(HERE, "config.toml"))
    argv = sys.argv[1:]
    extra = []
    if "--" in argv:            # everything after -- goes to the recorder or checker untouched
        k = argv.index("--")
        argv, extra = argv[:k], argv[k + 1:]
    a = ap.parse_args(argv)
    a.extra = extra
    if a.action == "record":
        cfg = tomllib.load(open(a.config, "rb"))
        s = cfg.get("servers", {}).get(a.server)
        if s is None:
            sys.exit(f"no [servers.{a.server}] in {a.config}")
        os.makedirs(a.out, exist_ok=True)
        argv = recorder_argv(a.suite, s, os.path.join(a.out, f"{a.suite}.jsonl")) + a.extra
    else:
        out_dir = os.path.join(a.indir, a.suite)
        os.makedirs(out_dir, exist_ok=True)
        argv = checker_argv(a.suite, os.path.join(a.indir, f"{a.suite}.jsonl"), out_dir, a.tlc) + a.extra
    print("+", " ".join(shlex.quote(x) for x in argv), file=sys.stderr)
    sys.exit(subprocess.call(argv))


if __name__ == "__main__":
    main()
