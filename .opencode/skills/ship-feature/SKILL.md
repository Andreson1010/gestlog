---
name: ship-feature
description: End-to-end delivery pipeline for this repo — branch, implement, test, open PR, MANDATORY code review, fix findings, squash-merge. Trigger with /ship-feature, or whenever the user asks to "ship", "deliver", "finish", or "merge" a feature/fix the full way through.
---

# Ship Feature

Seven steps, in order. Do not skip step 5. Do not commit to `main` directly — that is the #1 recurring failure this skill exists to prevent.

Read `AGENTS.md` at the repo root first for the exact branch naming, commit language, test commands, and gate thresholds.

---

## 1. Create feature branch

Never work on `main`. Branch off latest `main` first:

```bash
git checkout main
git pull origin main
git checkout -b feat/<short-name>   # or fix/<short-name> for bug fixes
```

Use the branch naming convention from `AGENTS.md` (e.g. `feat/`, `fix/`, `refactor/`, `data/`). Keep `<short-name>` kebab-case and descriptive. Follow the project's commit language and convention — when in doubt, match existing `git log` entries.

If currently on `main` with uncommitted work, branch first (`git checkout -b feat/<name>`), then commit — never commit to `main` and branch afterward.

---

## 2. Implement

Follow the `build-with-tests` skill:

- Read `AGENTS.md` and match the existing patterns for the layer you're touching (backend/frontend/config/data).
- No hardcoded values — everything configurable goes in the project's config module.
- Functions < 50 lines, nesting < 4 levels, immutable data where the project uses it.
- `from __future__ import annotations` on line 1 of every `.py` file.
- `pathlib.Path` for paths, `logger = logging.getLogger(__name__)` instead of `print()`.
- No comments outside docstrings unless the project allows them.
- Write tests alongside the code, not after.

Commit with the project's conventional commit format:

```bash
git add <specific files>
git commit -m "<type>(<scope>): <descrição curta>"
```

---

## 3. Run tests

Gate check — must pass before opening a PR. Use the commands from `AGENTS.md` / `Makefile`; the typical Python shape is:

```bash
uv run pytest          # full suite + coverage gate
uv run ruff check src/ tests/
uv run black src/ tests/
```

- All tests pass.
- Coverage stays at or above the project's threshold — write more tests if it drops, don't weaken assertions.
- New code has: happy path, empty/edge case, and failure-path tests.
- External services (LLM, HTTP, DB, vector store) are mocked — no test touches the network.
- Every boundary/empty-result path has a test.

If anything fails, fix it before proceeding. Do not open a PR with a red test suite.

---

## 4. Open PR

```bash
git push -u origin feat/<short-name>

gh pr create \
  --title "<type>(<scope>): <descrição curta>" \
  --body "$(cat <<'EOF'
## O que foi feito
- ...

## Por que foi feito
...

## Como testar
1. ...

## Checklist
- [ ] Testes passam
- [ ] Cobertura no alvo do projeto
- [ ] Sem credenciais/segredos no diff
- [ ] Lint ok
- [ ] Formatação ok
EOF
)"
```

Store the PR URL/number — needed for step 5.

---

## 5. MANDATORY code review

**Not skippable.** This is the step that has been missed before, causing findings to slip into merged code.

Invoke the local **`code-reviewer`** skill against the opened PR diff (`git diff origin/main...HEAD`). Wait for the report before doing anything else. Don't invoke a plugin/cloud review variant (e.g. "ultra") automatically — that's billed and user-triggered only.

Do not proceed to step 6/7 until the review has actually run and you have its findings in hand.

---

## 6. Fix findings

Route findings by severity:

| Severity | Action |
|---|---|
| Critical / Important | Fix now, on the same branch, before merge |
| Minor | Fix now if trivial, otherwise note in PR and let the user decide |

Push fixes as **new commits** (never amend/force-push a PR others may have pulled):

```bash
git add <files>
git commit -m "fix(scope): endereça apontamento do code review"
git push
```

If findings were Critical/Important, re-run step 5 (`code-review`) on the updated diff before moving on.

---

## 7. Squash-merge

Only after the review is clean (or all blocking findings addressed):

```bash
gh pr merge --squash
```

Then sync local `main` (per `AGENTS.md`):

```bash
git checkout main
git pull origin main
git branch -d feat/<short-name>
```

---

## Hard rules

1. **Branch before commit, always.** If you're on `main`, stop and branch first.
2. **Step 5 is mandatory.** A PR with no code-review report is not done.
3. **Critical/Important findings block merge.** Only Minor findings are optional.
4. **Squash-merge, then pull `main`.** Don't leave local `main` stale after merging.
5. **Never force-push or amend commits already pushed to the PR branch** — push new commits instead.
