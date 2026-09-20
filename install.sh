#!/bin/sh
# jevgrep installer.
#
#   curl -fsSL https://raw.githubusercontent.com/anup-a/jevgrep/main/install.sh | sh
#
# Prefers uv, falls back to pipx, then pip --user. Installs into an isolated
# environment so jevgrep's dependencies never touch your system Python.
set -eu

REPO_URL="${JEVGREP_REPO:-https://github.com/anup-a/jevgrep}"
REF="${JEVGREP_REF:-main}"
SPEC="git+${REPO_URL}@${REF}"

RED='\033[1;31m'
GREEN='\033[1;32m'
DIM='\033[2m'
RESET='\033[0m'
[ -t 1 ] || { RED=''; GREEN=''; DIM=''; RESET=''; }

say() { printf '%s\n' "$*"; }
die() { printf "${RED}error:${RESET} %s\n" "$*" >&2; exit 1; }

have() { command -v "$1" >/dev/null 2>&1; }

# Python 3.11+ is required; check whichever interpreter we would actually use.
check_python() {
  for candidate in python3.13 python3.12 python3.11 python3; do
    if have "$candidate" && "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
      return 0
    fi
  done
  return 1
}

say ""
say "  jevgrep — grep, but the pattern is a question in natural language."
say ""

if have uv; then
  say "${DIM}Installing with uv...${RESET}"
  uv tool install --force "$SPEC"
  BIN="$(uv tool dir 2>/dev/null)/../bin" || BIN=""
elif have pipx; then
  say "${DIM}Installing with pipx...${RESET}"
  pipx install --force "$SPEC"
elif check_python; then
  say "${DIM}uv and pipx not found; installing with pip --user.${RESET}"
  say "${DIM}Consider https://docs.astral.sh/uv/ for isolated installs.${RESET}"
  python3 -m pip install --user --upgrade "$SPEC"
else
  die "need uv, pipx, or Python 3.11+. See https://docs.astral.sh/uv/getting-started/"
fi

say ""
if have jevgrep; then
  printf "${GREEN}✓${RESET} installed: %s\n" "$(command -v jevgrep)"
else
  printf "${GREEN}✓${RESET} installed. If 'jevgrep' is not found, add your tool bin directory to PATH.\n"
  [ -n "${BIN:-}" ] && say "${DIM}  (uv usually installs to ~/.local/bin)${RESET}"
fi

say ""
say "Set a key from the Vercel AI Gateway, then try it:"
say ""
say "  export JEVGREP_API_KEY=..."
say "  printf 'disk almost full\\nbuild succeeded\\n' | jevgrep 'is this urgent?'"
say ""
