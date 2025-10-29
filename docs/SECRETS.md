# Secrets handling and how to avoid GitGuardian / pre-commit secret scanners

This document explains secure options for storing and supplying credentials to Docker, Compose and CI — without committing secrets to Git.

1) Never hardcode secrets in source
 - Files committed to Git are permanent unless you rewrite history. Secret scanners (GitGuardian, TruffleHog, etc.) will flag secrets and can block PRs.
 - If secrets were already committed, rotate them immediately and remove them from history (see section below).

2) Preferred runtime approaches (no secrets in repo)
 - Environment variables (recommended for local dev):
   - Keep a local `.env` file (listed in `.gitignore`) and never commit it.
   - Use `.env.example` in the repo with placeholders so other developers know which variables to create.
 - Docker Compose and env vars:
   - Reference variables in your `docker-compose.yml` like:
     ```${DB_PASSWORD}``` or `${DB_USERNAME:-default}`
   - At runtime `docker-compose` will load `.env` in the compose directory and substitute variables.
 - Docker secrets (recommended for production on Swarm/Kubernetes/compose v3+):
   - For Docker Swarm or Kubernetes, use native secrets support and avoid environment variables where possible.
 - CI/CD secret stores (recommended for CI pipelines):
   - GitHub Actions: store secrets in repository or organization Secrets and inject them as env vars at workflow runtime.
   - GitLab CI/CD, Azure DevOps, CircleCI, etc. provide similar secret storage.

3) If you need to remember credentials
 - Use a password manager (Bitwarden, 1Password, KeePassXC). They are secure and let you share credentials with team members.
 - Do NOT keep plaintext passwords in the repo for convenience.

4) How to avoid GitGuardian alerts when opening PRs
 - Remove any secret values from the files that appear in your PR. Replace with env var references or placeholders.
 - If a secret was accidentally committed:
   1. Rotate the secret immediately (invalidate the old credential).
   2. Remove the secret from the git history using an approved tool and push a forced update to the branch (coordinate with your team):
      - BFG Repo-Cleaner (easier) or git-filter-repo (recommended). Example (you must run locally):
        - Install `git-filter-repo` then run: `git filter-repo --path <file-containing-secret> --invert-paths` to remove file, or use `--replace-text` for patterns.
        - Or use BFG: `bfg --replace-text replacements.txt` where `replacements.txt` contains the secret to remove.
   3. After rewriting history, force-push the branch and re-open PRs. Note: this rewrites commits and requires coordination.

5) Suggested immediate repo changes (what I added)
 - `.env.example` — placeholders so no real credentials are in the repo.
 - `.gitignore` already ignores `.env` and common key files (the repository already contains rules to prevent accidental commits of `.env`).

6) Example workflow for local development
 - Create `.env` from `.env.example` locally:
   - `cp .env.example .env` (or create on Windows with copy)
   - Fill in secrets locally or use your OS keyring to inject env vars.
 - Start Compose: `docker-compose -f docker-compose.bldg1.yml up -d` — Compose will use the `.env` file for substitutions.

7) Example: how to reference env vars in `docker-compose.yml`
 - service example snippet:
   ```yaml
   services:
     db:
       image: postgres:13
       environment:
         - POSTGRES_USER=${DB_USERNAME}
         - POSTGRES_PASSWORD=${DB_PASSWORD}
         - POSTGRES_DB=ontobot
   ```

8) For production/CI: use GitHub Actions secrets
 - Example GH Actions snippet to pass secret to Docker build/run or to a deploy step:
   ```yaml
   env:
     DB_USERNAME: ${{ secrets.DB_USERNAME }}
     DB_PASSWORD: ${{ secrets.DB_PASSWORD }}
   ```

9) If GitGuardian already flagged your PR
 - If the flagged secret is in your branch but not in repo history (i.e., in current commit only), remove it, force-push, and re-open PR.
 - If it was in history, rotate the secret first (so leaked value is no longer valid), then remove from history and push.

10) Helpful references
 - GitHub Secrets: https://docs.github.com/en/actions/security-guides/encrypted-secrets
 - Docker Compose env: https://docs.docker.com/compose/environment-variables/
 - git-filter-repo: https://github.com/newren/git-filter-repo
 - BFG Repo-Cleaner: https://rtyley.github.io/bfg-repo-cleaner/

If you'd like, I can:
 - Update `docker-compose.bldg1.yml` to reference env variables (no credentials added),
 - Create a `.env.example` (already added), and
 - Provide commands to rotate or remove secrets from history based on whether secrets already exist in commits.

Tell me which of the above you'd like me to do next.
