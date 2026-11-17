#!/usr/bin/env python3
"""Reduce recorded SASL traces to what SpecSasl judges, for comparing servers.

  summarize.py TRACE.jsonl [...] [--json OUT]

For each scenario and connection, keeps the server's SASL numerics (900-908),
its AUTHENTICATE lines and its CAP NEW/DEL lines, in order, with nicks,
accounts, hosts and server names replaced by placeholders. Two runs of the
same recorder against two builds then compare line for line (compare.py).
"""
import json, re, sys

SASL_NUM = {str(n) for n in range(900, 909)}


def reduce_line(raw, names):
    """Return the reduced form of one server line, or None to drop it."""
    raw = re.sub(r"^@\S+ ", "", raw)
    parts = raw.split(" ")
    if parts and parts[0].startswith(":"):
        parts = parts[1:]
    if not parts:
        return None
    cmd = parts[0]
    if cmd in SASL_NUM:
        return cmd
    if cmd == "AUTHENTICATE":
        return "AUTHENTICATE " + ("+" if parts[1:] == ["+"] else "<data>")
    if cmd == "CAP" and len(parts) > 2 and parts[2] in ("NEW", "DEL"):
        caps = " ".join(parts[3:]).lstrip(":").split()
        return f"CAP {parts[2]} " + " ".join(sorted(caps))
    return None


def summarize(path):
    out = {}
    for row in open(path):
        r = json.loads(row)
        if r.get("kind") != "trace":
            continue
        for conn in sorted({l["conn"] for l in r["lines"]}):
            seq = [x for x in (reduce_line(l["raw"], None) for l in r["lines"]
                               if l["conn"] == conn and l["dir"] == "S") if x]
            out[f"{r['name']}/{conn}"] = seq
    return out


def main():
    args = sys.argv[1:]
    out_json = None
    if "--json" in args:
        k = args.index("--json")
        out_json = args[k + 1]
        del args[k:k + 2]
    merged = {}
    for f in args:
        merged.update(summarize(f))
    for k, seq in merged.items():
        print(f"{k:40} {' '.join(seq) or '(nothing)'}")
    if out_json:
        json.dump(merged, open(out_json, "w"), indent=1)


if __name__ == "__main__":
    main()
