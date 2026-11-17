#!/usr/bin/env python3
"""Compare a candidate build against a base build, suite by suite.

  compare.py BASE_DIR CAND_DIR [--suite NAME ...] [--json OUT]

Each directory holds one subdirectory per suite with that suite's check
output, as the checkers write it:

  handshake/summary.json        check/handshake/check.py WORKDIR output
  registration/check.json       check/registration/check.py --json
  sasl/summary.json             check/sasl/summarize.py --json
  history-servers/check.json    check/history-servers/check.py --json

For every item a suite checks (a trace, a scenario, a query), the item's
verdict on the base is set against its verdict on the candidate. A failure
present on the candidate only is NEW; one present on the base only is FIXED;
a SASL reply sequence that differs is CHANGED. The exit status is 1 when any
suite has a NEW failure, so a CI job or a release script can gate on it.
"""
import argparse, json, os, sys


def load(path):
    with open(path) as f:
        return json.load(f)


def handshake(path):
    """name -> 'match' or the failing verdict; reauth columns kept as detail."""
    out = {}
    for s in load(os.path.join(path, "summary.json")):
        out[s["name"]] = (s["verdict"], f"R=F:{s.get('reauthFalse')} R=T:{s.get('reauthTrue')}")
    return {k: v[0] for k, v in out.items()}, {k: v[1] for k, v in out.items()}


def registration(path):
    d = load(os.path.join(path, "check.json"))
    verdict, detail = {}, {}
    for r in d["results"]:
        key = f"{r['name']}/{r['conn']}"
        real = sorted(rule for rule, v in r["rules"].items() if not v["probe"])
        verdict[key] = "ok" if not real else "finding:" + ",".join(real)
        detail[key] = "; ".join(f"{rule}: {'; '.join(v['why'])}" for rule, v in r["rules"].items())
    return verdict, detail


def history_servers(path):
    d = load(os.path.join(path, "check.json"))
    verdict = {}
    # One item per query index and property: the query matrix is the same on
    # every run of drive.py, so indices line up across builds.
    for dev in d.get("deviations", []):
        verdict[f"{dev['prop']}#{dev['i']}"] = "fail"
    for prop, c in d.get("props", {}).items():
        verdict[f"{prop} (counts)"] = f"pass={c['pass']} fail={c['fail']} na={c['na']}"
    return verdict, {}


def sasl(path):
    d = load(os.path.join(path, "summary.json"))
    return {k: " ".join(v) for k, v in d.items()}, {}


SUITES = {
    "handshake": (handshake, lambda v: v == "match"),
    "registration": (registration, lambda v: v == "ok"),
    "history-servers": (history_servers, None),
    "sasl": (sasl, None),
}


def compare(name, base_dir, cand_dir):
    fn, ok = SUITES[name]
    b, _ = fn(os.path.join(base_dir, name))
    c, _ = fn(os.path.join(cand_dir, name))
    rows = []
    for key in sorted(set(b) | set(c)):
        bv, cv = b.get(key, "(absent)"), c.get(key, "(absent)")
        if bv == cv:
            continue
        if ok is not None:
            if ok(bv) and not ok(cv):
                kind = "NEW"
            elif not ok(bv) and ok(cv):
                kind = "FIXED"
            else:
                kind = "CHANGED"
        elif name == "history-servers" and key.endswith("(counts)"):
            kind = "CHANGED"
        elif name == "history-servers":
            kind = "NEW" if cv == "fail" else "FIXED"
        else:
            kind = "CHANGED"
        rows.append({"suite": name, "item": key, "kind": kind, "base": bv, "candidate": cv})
    return {"suite": name, "items_base": len(b), "items_candidate": len(c), "differences": rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("candidate")
    ap.add_argument("--suite", action="append", choices=sorted(SUITES))
    ap.add_argument("--json")
    a = ap.parse_args()
    suites = a.suite or [s for s in SUITES
                         if os.path.isdir(os.path.join(a.base, s)) and os.path.isdir(os.path.join(a.candidate, s))]
    report, new = [], 0
    print(f"{'suite':16} {'items':>11} {'new':>4} {'fixed':>5} {'changed':>7}")
    for s in suites:
        r = compare(s, a.base, a.candidate)
        report.append(r)
        n = {k: sum(d["kind"] == k for d in r["differences"]) for k in ("NEW", "FIXED", "CHANGED")}
        new += n["NEW"]
        print(f"{s:16} {r['items_base']:>5}/{r['items_candidate']:<5} {n['NEW']:>4} {n['FIXED']:>5} {n['CHANGED']:>7}")
    for r in report:
        for d in r["differences"]:
            print(f"  {d['kind']:7} {d['suite']}: {d['item']}\n          base: {d['base']}\n     candidate: {d['candidate']}")
    if a.json:
        json.dump(report, open(a.json, "w"), indent=1)
    sys.exit(1 if new else 0)


if __name__ == "__main__":
    main()
