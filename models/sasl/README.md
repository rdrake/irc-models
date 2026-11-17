# sasl: `SpecSasl.tla`

IRCv3 SASL beyond the handshake model: several mechanisms and the `sasl=` list, 908 and retrying, AUTHENTICATE chunking in both directions, SCRAM-shaped mechanisms, 900-908, reauthentication after registration, and NEW/DEL of sasl.

## Files and checks

`RULES.md` lists each rule with its spec source and how the model encodes it.

`make-configs.py` is the single source of every `.cfg` and checks each against the module; `mutants/make-mutants.py` writes the mutants. Rerun both after any change to the module.

Server check: `harness/sasl/record_sasl.py` records (passwords never reach a trace); `check/sasl/summarize.py` reduces each scenario to its SASL numerics and CAP NEW/DEL lines, which `compare.py` sets against another build.
