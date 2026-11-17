# registration: `SpecReg.tla`

The rest of registration, spec first: PASS and 464, a server's PING cookie, 433 during registration, the registration timeout, and `draft/metadata-2` metadata set before registration against CAP END and the burst.

## Files and checks

`RULES.md` lists each rule with its spec source and how the model encodes it.

`make-configs.py` writes every `.cfg`; `mutants/make-mutants.py` writes the mutants. `Tiny*` configs run on a laptop (`runner/local.sh`); `Reference` needs the test runner. `W_*` are witnesses.

Server check: `harness/registration/record_reg.py` records; `check/registration/check.py` checks each connection against the model's wire rules (`Rule*`), and reports the recorder's deliberate client-rule probes separately.
