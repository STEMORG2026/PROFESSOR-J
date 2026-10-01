# DEBT — Technical Debt Tracker

> Found during the 2026-10-01 bootstrap audit. Severity: 🔴 high · 🟠 med · 🟡 low.

| ID | Debt | Sev | Location | Notes / remediation |
|---|---|---|---|---|
| D1 | **Interpreter mismatch.** Local dev venv is Python **3.14.7**; CI runs **3.11**. The local gate can pass where CI fails for reasons unrelated to the change. | 🟠 | dev environment | Standardise, or run the gate under 3.11 locally too |
| D2 | **`requirements.txt` had been uninstallable** since the OTel pins diverged — CI never reached a test. | 🔴 | `requirements.txt` | FIXED `9f690a2`; guard: `pip install --dry-run` in the gate |
| D3 | **Undeclared direct dependency**: `types-PyYAML` present in dev venvs only. `PyYAML` itself is also not declared (arrives transitively via 11 packages). | 🟠 | `requirements.txt` | Declare both |
| D4 | **Latent safety-gate bypass.** `web`/`browser`/`computer_use` are built at startup and hung on `AppRoot` but never registered with `ToolExecutor`. `computer_use.launch()` is `subprocess.Popen(app.split())`. Unreferenced today; one line of future code makes it live. | 🟠 | `app/bootstrap.py:250-285`, `app/tools/` | Gate at DESTRUCTIVE/SENSITIVE, or delete |
| D5 | **Floating pins cause CI/local divergence**: `pymupdf>=1.28.2`, `langgraph>=1.2.11`, `chromadb>=1.5.9` (while the repo mostly uses `==`). `pdf.py:59`'s type-ignore is sensitive to this. | 🟠 | `requirements.txt` | Pin to the versions in use |
| D6 | **`ci.yml` and `gate-mirror.yml` overlap**, so they will drift. | 🟡 | `.github/workflows/` | Consolidate, or make one clearly authoritative |
| D7 | **`ci.yml` `Tests` job fails on coverage** (76% vs its own `--cov-fail-under=80`) — a threshold with no owner. | 🟡 | `.github/workflows/ci.yml` | Align with the gate's floors or revise |
| D8 | **Environment-dependent tests are declared as permanent defects**, so the declared baseline is not portable. | 🟠 | `scripts/declared_defects.py`, `tests/unit/knowledge/`, `tests/unit/voice/` | Make hermetic fixtures |
| D9 | **`Security scan` job fails**, cause not yet diagnosed. | 🟠 | `.github/workflows/ci.yml` | Diagnose next session |
| D10 | 3 pre-existing **git stashes** from earlier agents are unlabelled and unmerged. | 🟡 | `.git` | Triage or drop deliberately |
| D11 | **`docs/ARCHITECTURE-ESSENTIALS.md` reference-style link bug**: `README.md` pointed at a nonexistent `docs/ARCHITECTURE-ESSENTIALS.md` (fixed). The docs checker does not catch reference-style links — a real gap. | 🟡 | `scripts/docs/check_docs.py` | Teach the checker reference definitions |
