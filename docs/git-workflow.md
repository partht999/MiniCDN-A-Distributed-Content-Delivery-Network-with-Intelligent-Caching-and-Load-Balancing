# Team Git workflow

The project already has a Git repository and origin/fork remotes. The existing branch is feature/phase0-prototype. Preserve existing history and changes when creating further branches.

Use short branches such as codex/phase4-completion for the integration increment, and feature/cache-disk or feature/routing-budget for isolated follow-ups. Start from the tested integration revision, commit a coherent change with its relevant tests, review the diff, and merge through a reviewed pull request when your team's remote workflow is available. Do not force-push shared history.

Commit subjects: `feat: add ...`, `fix: prevent ...`, `test: verify ...`, `docs: describe ...`. State the actual behavior rather than a generic phase number. Keep generated runtime files and passwords out of Git. Keep experiment seeds, methodology, small summary datasets, report sources and tests versioned. Raw experimental samples can be archived alongside the tested commit.

Before integration: gofmt, go test ./..., Go 1.21 Docker compatibility check, race check, Compose config validation, relevant functional smoke tests, git diff --check. Only rerun broad performance comparisons when policy/cache behavior or the tested environment changes.

Record actual reviewer, commit hash, test commands, date and result in the team progress record. A convention document alone is not evidence that team review/branching happened.
