# irc-models

TLA+ models of IRCv3 client–server behaviour, and the tools to check a real
IRC server against them: recorders that drive a live server through the
scenarios a model cares about, checkers that judge each recorded trace
(directly and by TLC trace validation), and a compare step that sets one
build against another.

It is meant to sit next to [irctest](https://github.com/progval/irctest):
irctest asks "does the server answer this command correctly?", these models
ask "is every sequence of lines the server can produce one the spec allows?"
Nothing here is specific to one ircd. Server-specific setup lives in
`harness/*/` controllers and in your local `config.toml`.

## What is modelled

| Area | Model | What it covers | Server check |
| --- | --- | --- | --- |
| [handshake](models/handshake/) | `SpecHandshake.tla` | CAP 302, cap-notify, SASL 3.1/3.2 during registration | `harness/handshake/drive.py` + `check/handshake/check.py` (TLC) |
| [registration](models/registration/) | `SpecReg.tla` | PASS, PING cookies, 433, timeouts, `draft/metadata-2` before-connect | `harness/registration/record_reg.py` + `check/registration/check.py` |
| [sasl](models/sasl/) | `SpecSasl.tla` | mechanisms and `sasl=`, chunking, 900–908, reauthentication, NEW/DEL | `harness/sasl/record_sasl.py` + `check/sasl/summarize.py` |
| [history](models/history/) | `History.tla`, `Delivery.tla`, `Edit.tla` | CHATHISTORY paging and a client's catch-up; labeled-response, echo-message and batch for a client's own messages; edits | `harness/history-servers/drive.py` + `check/history-servers/check.py` (TLC) |

Rules cite the IRCv3 specification sources by file and line (`CN:355` is line
355 of `extensions/capability-negotiation.md`, `CH:` chathistory, `BA:` batch,
`LR:` labeled-response, `MD:` metadata, `MI:`/`MC:` Modern IRC). Each area's
`RULES.md` names the ircv3-specifications commit it was read at. `D`/`Q`
numbers in model comments refer to the design decision log, which is not
published yet.

Client-side models (a client's session state, reconnect and STS, a client's
own handshake) and client drivers live in the clients' repositories and use
this one.

## Layout

```
models/<area>/      the .tla modules, their .cfg files, mutants/ and the config generators
harness/<suite>/    recorders: drive a live server, write one JSON object per line
check/<suite>/      checkers: judge recorded traces (Python properties, TLC trace validation)
runner/             TLC runs: local.sh on this machine, remote.py + slurm/ on a test runner
run.py              record or check one suite against a server named in config.toml
compare.py          base build against candidate build, every suite, one table
ci/                 scrub.py (what may be published) and the pre-commit hook
```

## Quick start

Python 3.11+, Java 17+ and `tla2tools.jar` (set `TLA_JAR`) for anything that runs TLC.

```sh
cp config.example.toml config.toml        # name your server(s), accounts and runner
./run.py record history-servers --server local --out out/base
./run.py check  history-servers --in out/base --tlc
# rebuild the server, then
./run.py record history-servers --server local --out out/cand
./run.py check  history-servers --in out/cand --tlc
./compare.py out/base out/cand            # exit 1 if the candidate fails anything the base passed
```

Small model configs run locally:

```sh
runner/local.sh models/registration SpecReg TinyPass
```

Large ones go to a Slurm test runner, from a pinned commit:

```sh
runner/remote.py sync handshake           # prints the run folder, e.g. handshake-1a2b3c4d5e
runner/remote.py submit handshake-1a2b3c4d5e tlc-resume.sbatch Reference
runner/remote.py fetch  handshake-1a2b3c4d5e out/runs/handshake-1a2b3c4d5e
```

## Recordings and results

Recorded traces and check results are not kept here: they name test servers
and accounts, and can show server bugs before they are reported. Report a
server bug to its project first; a trace that shows a filed bug can then be
added as a fixture.

## Contributing

Run `ci/scrub.py` before pushing, or install the `ci/pre-commit` and
`ci/commit-msg` hooks. CI scrubs every file and commit message, parses
every module with SANY and runs the checkers' self-tests.

## Licence

MIT, see [LICENSE](LICENSE).
