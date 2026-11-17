#!/usr/bin/env python3
"""Compare a candidate build against a base build, suite by suite.

  compare.py BASE_DIR CAND_DIR [--suite NAME ...] [--json OUT]

Each directory holds one subdirectory per suite with that suite's check
output, as the checkers write it:

  handshake/summary.json        check/handshake/check.py WORKDIR output
  registration/check.json       check/registration/check.py --json
  sasl/summary.json             check/sasl/summarize.py --json
  history-servers/check.json    check/history-servers/check.py --json

For every item a suite checks (a trace, a scenario's connection, a kind of
history deviation), the item's verdict on the base is set against its verdict
on the candidate. A failure present on the candidate only is NEW; one present
on the base only is FIXED. A SASL reply sequence that differs, or an item only
one run has, is CHANGED: it has no pass/fail reading and needs a person. The
exit status is 1 when any suite has a NEW failure, so a CI job or a release
script can gate on it; read the CHANGED lines too.
"""
import argparse, json, os, re, sys
from collections import Counter, defaultdict


def load(path):
    with open(path) as f:
        return json.load(f)


def handshake(path):
    """name -> 'match' or the failing verdict; reauth columns kept as detail."""
    out = {}
    for s in load(os.path.join(path, "summary.json")):
        out[s["name"]] = (s["verdict"], f"R=F:{s.get('reauthFalse')} R=T:{s.get('reauthTrue')}")
    return {k: v[0] for k, v in out.items()}, {k: v[1] for k, v in out.items()}


def ordinal_keys(pairs):
    """[(scenario, conn, value)] -> {"scenario#k": value}, k counting the
    scenario's connections from 1 in connection order. The recorders number
    connections with one counter for the whole run, so the same connection
    can be c13 on one run and c15 on another (a skipped scenario before it);
    its place within its own scenario does not move."""
    by = defaultdict(list)
    for name, conn, v in pairs:
        by[name].append((int(re.sub(r"\D", "", conn) or 0), v))
    return {f"{name}#{k}": v for name, rows in by.items()
            for k, (_, v) in enumerate(sorted(rows), 1)}


def registration(path):
    d = load(os.path.join(path, "check.json"))
    pairs = []
    for r in d["results"]:
        real = sorted(rule for rule, v in r["rules"].items() if not v["probe"])
        pairs.append((r["name"], r["conn"], "ok" if not real else "finding:" + ",".join(real)))
    return ordinal_keys(pairs), {}


def history_servers(path):
    """One item per kind of deviation: (property, the query's role in the
    matrix, the command with run id, msgids and timestamps blanked), counted.
    Query indices are not stable across builds (follow-ups and walks depend
    on the replies), so they are not used. Property counts are items too."""
    d = load(os.path.join(path, "check.json"))
    runid = d.get("meta", {}).get("runid") or "\x00"

    def shape(cmd):
        cmd = cmd.replace(runid, "<run>")
        cmd = re.sub(r"msgid=\S+", "msgid=<m>", cmd)
        return re.sub(r"timestamp=\S+", "timestamp=<t>", cmd)

    count = Counter(f"{dev['prop']} [{dev.get('note', '')}] {shape(dev.get('cmd', ''))}"
                    for dev in d.get("deviations", []))
    verdict = {k: n for k, n in count.items()}
    for prop, c in d.get("props", {}).items():
        verdict[f"{prop} (fail count)"] = c["fail"]
    return verdict, {}


def sasl(path):
    d = load(os.path.join(path, "summary.json"))
    pairs = [(k.rsplit("/", 1)[0], k.rsplit("/", 1)[1], " ".join(v)) for k, v in d.items()]
    return ordinal_keys(pairs), {}


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
        if name == "history-servers":
            # values are failure counts: more on the candidate is NEW
            nb, nc = (bv if isinstance(bv, int) else 0), (cv if isinstance(cv, int) else 0)
            kind = "NEW" if nc > nb else "FIXED"
        elif ok is not None and bv != "(absent)" and cv != "(absent)":
            kind = "NEW" if ok(bv) and not ok(cv) else "FIXED" if ok(cv) and not ok(bv) else "CHANGED"
        else:
            # SASL reply sequences, and items only one run has: no pass/fail
            # reading, reported for a person to judge
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
