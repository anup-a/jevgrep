#!/usr/bin/env bash
# Demo driver for the asciinema recording. Types each command out, runs it, pauses.
#
#   asciinema rec demo.cast --window-size 128x28 -c examples/demo.sh
#
# Cut for social: opens on the grep comparison, no preamble. Expects jevgrep on
# PATH and TYPESAFE_API_KEY exported.
set -u

TYPE_DELAY=${TYPE_DELAY:-0.022}
PAUSE=${PAUSE:-1.9}

note() { printf '\033[38;5;245m# %s\033[0m\n' "$1"; sleep 0.9; }

run() {
  printf '\033[1;32m❯\033[0m '
  local i
  for ((i = 0; i < ${#1}; i++)); do
    printf '%s' "${1:i:1}"
    sleep "$TYPE_DELAY"
  done
  printf '\n'
  sleep 0.5
  eval "$1"
  printf '\n'
  sleep "$PAUSE"
}

clear
sleep 0.6

run "grep -cE 'ERROR|WARN' examples/auth.log"
note "Seven. A regex can only match spelling."
sleep 0.5

run "jevgrep --explain 'is this an authentication failure?' examples/auth.log"
note "Four. The 500, the pool exhaustion and the rate limit are gone."
sleep 0.7

run "jevgrep --json --explain 'is this role fully remote AND paid in US dollars?' examples/jobs.jsonl"
note "Compound predicate over JSON. No embeddings. No index."
sleep 0.7

run "jevgrep --whole --explain -t 0.4 'does this module make outbound network requests?' src/jevgrep/*.py"
note "The red one: it does not know. --min-confidence turns that into a non-match, not a guess."
sleep 0.9
printf '\033[1;32m❯\033[0m \033[1mjevgrep\033[0m — grep, but the pattern is a question.\n'
sleep 2.4
