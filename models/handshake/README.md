# handshake: `SpecHandshake.tla`

Connection registration as the IRCv3 specs describe it: CAP LS 302 and its continuation lines, REQ/ACK/NAK, cap-notify NEW/DEL, SASL 3.1 and 3.2 (900-908, `*` aborts, reauthentication), and the client's CAP END. No particular server or client is modelled: every server choice the spec leaves open is a nondeterministic choice in the model.

## Files and checks

`RULES.md` lists each rule with its spec source and how the model encodes it.

Each `.cfg` is one check. `Reference` and the `Ref*` configs are the full safety and liveness runs (large: use the test runner, `split-env.py` slices them by environment). `W_*` configs are witnesses: TLC must find a trace (they are listed as `fail` in a bundle list). `mutants/` holds copies of the module with one rule broken; each must be caught by at least one config.

Trace validation of a live server: `harness/handshake/drive.py` records, `check/handshake/check.py TRACES WORKDIR` replays each trace through the model with `Reauth` off and on.
