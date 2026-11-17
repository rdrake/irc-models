# history: `History.tla`

`History.tla`: a client's catch-up over CHATHISTORY (pages, held lines, the live line, reconnects) and the server obligations it relies on. `Delivery.tla`: a client's own messages under labeled-response, echo-message and batch. `Edit.tla`: message edits.

## Files and checks

`RULES.md` lists each rule with its spec source and how the model encodes it.

Generators: `mkhist.py` (History variants `HC_*`, `HS_*`, `HV_*`, `HR_*` and their configs), `mkmut.py` (Delivery mutants `DM_*`, `DS_*`), `mkedit.py` (Edit variants `EM_*`). `list-*` files are bundle lists for `runner/slurm/tlc-bundle.sbatch`: one `<module> <config> <pass|fail>` per line.

Server check: `harness/history-servers/drive.py` seeds channels and runs a query matrix; `check/history-servers/check.py OBS.jsonl [--tlc WORKDIR]` checks every reply against the server obligations, and with `--tlc` validates the small channel's pages against `History.tla`. `check/history-catchup/` checks a client's catch-up traces; `check/labeled-response/` checks raw labeled-response recordings.
