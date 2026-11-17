#!/bin/bash
# Run TLC on one model and config on this machine. For the small configs and
# trace checks only: the large configs need the test runner (remote.py).
#
#   runner/local.sh models/registration SpecReg Reference [extra TLC flags]
#
# TLA_JAR points at tla2tools.jar (default ~/tools/formal/tla2tools.jar).
set -euo pipefail
DIR="${1:?model folder}"; MOD="${2:?module}"; CFG="${3:?config}"; shift 3
JAR="${TLA_JAR:-$HOME/tools/formal/tla2tools.jar}"
[ -f "$JAR" ] || { echo "no tla2tools.jar at $JAR (set TLA_JAR)" >&2; exit 2; }
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
cp "$DIR"/*.tla "$DIR"/*.cfg "$WORK"/
[ -d "$DIR/mutants" ] && cp "$DIR"/mutants/*.tla "$WORK"/ 2>/dev/null || true
cd "$WORK"
exec java -XX:+UseParallelGC -cp "$JAR" tlc2.TLC -workers auto -metadir states \
  -config "$CFG.cfg" "$MOD.tla" "$@"
