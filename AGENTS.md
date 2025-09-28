# GIT

## Pull Request
When making pull requests, here are things to consider:
1. Write some comments on core changes
2. Ensure the feature branch is rebased on the latest main branch (resolving conflicts locally before pushing).
3. Double-check the diff so only intentional files are included (no stray or temporary artifacts).
4. Execute relevant tests/build steps, collect results, and include them in the PR description.
5. Summarize user-visible changes and highlight new configuration options or flags (e.g., CLI/env vars).

## Merge
When merging PR, here are things to consider:
1. Review the comments and notes owithin PR.
2. If the change seems not logical to you, reject and write/give proper reason.
3. If seems ok, merge
