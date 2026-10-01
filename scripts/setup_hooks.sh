#!/usr/bin/env bash
#
# Install the repository's git hooks.
#
# The hooks live in `githooks/` rather than `.git/hooks/` so they are version-controlled, reviewed
# in the same pull requests as the rules they enforce, and identical for every contributor. A hook
# that only exists on one machine is not a policy.
#
# This installs `core.hooksPath = githooks`, which makes git run EVERY hook in that directory.
# Note the consequence: a `.git/hooks/pre-push` is then ignored entirely, and `--no-verify` is the
# only way past — which the hook itself refuses.
#
# The same redirection means hooks installed by the `pre-commit` framework into `.git/hooks/`
# (from .pre-commit-config.yaml) will NO LONGER RUN. That is a real behaviour change, not a
# footnote: this script does not silently disable anything without saying so. There is currently no
# `githooks/pre-commit`, so nothing runs at commit time. See docs/700-open-work.md 3.6.
#
# Usage: bash scripts/setup_hooks.sh [--check]

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

WANT="githooks"
CURRENT="$(git config --get core.hooksPath || true)"

if [ "${1:-}" = "--check" ]; then
  if [ "$CURRENT" = "$WANT" ]; then
    echo "hooks: INSTALLED (core.hooksPath=$CURRENT)"
    exit 0
  fi
  echo "hooks: NOT INSTALLED (core.hooksPath=${CURRENT:-<unset>})"
  echo "run: bash scripts/setup_hooks.sh"
  exit 1
fi

if [ "$CURRENT" = "$WANT" ]; then
  echo "core.hooksPath is already '$WANT' — nothing to do."
else
  git config core.hooksPath "$WANT"
  echo "set core.hooksPath = $WANT"
fi

# Hooks must be executable; a non-executable hook is silently skipped by git, which is exactly the
# failure mode this whole system exists to prevent. Check, do not assume.
chmod +x githooks/* 2>/dev/null || true
# `|| true` here is safe: it covers "no files matched" and the explicit verification below is what
# actually decides success. It cannot mask a broken hook.

missing=0
for h in githooks/*; do
  [ -f "$h" ] || continue
  if [ ! -x "$h" ]; then
    echo "ERROR: $h is not executable; git would silently skip it." >&2
    missing=1
  fi
done
[ "$missing" -eq 0 ] || exit 1

echo
echo "Installed hooks:"
for h in githooks/*; do
  [ -f "$h" ] && echo "  $(basename "$h")"
done
echo
echo "Verify with:  bash githooks/pre-push --self-test"
echo "The pre-push hook runs the full gate and has no bypass flag."
echo
echo "NOTE: core.hooksPath=$WANT supersedes hooks in .git/hooks/, so anything installed by"
echo "      'pre-commit install' will not run. There is no githooks/pre-commit yet."
echo "      See docs/700-open-work.md section 3.6."
