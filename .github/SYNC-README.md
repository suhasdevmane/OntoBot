# Sync setup for OntoSage-docs.github.io

This repository is automatically synchronized hourly from:

- Source: https://github.com/suhasdevmane/suhasdevmane.github.io
- Target: https://github.com/OntoSage-docs/OntoSage-docs.github.io

## How it works

- A GitHub Actions workflow at `.github/workflows/sync-from-source.yml` clones the source repo,
  mirrors its files into this repo, and pushes changes to `main`.
- The workflow excludes `.github/` (to preserve workflows/docs in this folder) and `CNAME`.
- It runs hourly and can be triggered manually via the Actions tab ("Run workflow").

## Manual run

1) Go to Actions → "Sync from primary repo" → Run workflow.
2) Wait for the job to finish; if it commits changes, you'll see a push to `main`.

## Notes

- Any files added to the root that are not present in the source will be removed on the next sync.
  Place persistent, target-only documentation under `.github/` to keep it.
- GitHub Pages for this repository publishes from the root of the default branch.