#!/usr/bin/env bash
# Demo driver for the asciinema recording. Types each command out, runs it, pauses.
#
#   asciinema rec demo.cast -c examples/demo.sh
#
# Expects jevgrep on PATH and TYPESAFE_API_KEY exported.
set -u

TYPE_DELAY=${TYPE_DELAY:-0.018}
PAUSE=${PAUSE:-1.6}

say() { printf '\033[2m# %s\033[0m\n' "$1"; sleep 1.0; }

run() {
  printf '\033[32m$\033[0m '
  local i
  for ((i = 0; i < ${#1}; i++)); do
    printf '%s' "${1:i:1}"
    sleep "$TYPE_DELAY"
  done
  printf '\n'
  sleep 0.4
  eval "$1"
  printf '\n'
  sleep "$PAUSE"
}

clear
say "grep, but the pattern is a question in English."
printf '\n'
sleep 0.8

say "A regex over a log can only match spelling, so it over-matches."
run "grep -cE 'ERROR|WARN' examples/auth.log"

say "Seven hits. But how many are actually auth failures?"
run "jevgrep -c 'is this line an authentication or login failure?' examples/auth.log"

say "Four. Here they are, with the probability and the model's own confidence."
run "jevgrep --explain -n 'is this line an authentication or login failure?' examples/auth.log"

say "It rejected the HTTP 500, the pool exhaustion and the rate limit."
say "Same interface as grep, so it composes. JSON records, compound predicate:"
run "jevgrep --json --explain 'is this role fully remote AND paid in US dollars?' examples/jobs.jsonl"

say "Remote-but-euros and dollars-but-onsite both correctly dropped."
say "Point it at source files, one record per file:"
run "jevgrep --whole --explain --min-confidence 0.5 'does this module make outbound network requests?' src/jevgrep/*.py"

say "Note the uncertain line. --threshold asks how probable the answer is;"
say "--min-confidence asks how sure the model is. Low confidence never matches,"
say "in either direction, so ambiguous records get escalated, not guessed at."

say "And the exit codes are grep's, so it drops straight into a shell:"
run "jevgrep -q 'is this about ssh?' examples/auth.log && echo 'found one'"

say "No embeddings. No index. ~200ms and \$0.00002 a record."
sleep 2
