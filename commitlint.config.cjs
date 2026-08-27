// Shared commit message conventions for PROFESSOR-J.
// Used by the wagoid/commitlint-github-action CI check on pull requests.
// Pure rule config (no external parser preset) so it runs without extra deps.
"use strict";

module.exports = {
  rules: {
    "header-max-length": [2, "always", 100],
    "type-enum": [
      2,
      "always",
      ["feat", "fix", "docs", "refactor", "test", "chore", "build", "ci", "perf", "style", "revert", "merge"],
    ],
    "type-case": [2, "always", "lower-case"],
    "type-empty": [2, "never"],
    "subject-empty": [2, "never"],
    "subject-full-stop": [2, "never", "."],
    "body-leading-blank": [1, "always"],
    "footer-leading-blank": [1, "always"],
  },
};
