# Sandhātā GitHub and Collaboration Guide

Version 0.1 | October 26 2026 | Prepared for Hema Chepuri | Design baseline

This document specifies the intended implementation. Application code, test results, live integrations, GitHub publication and production deployment are not established by this document. Dates are delivery targets in America/New_York, subject to the release gates.

## Repository destination

The owner created https://github.com/hemach-git/sandhata and will run the network Git commands collaboratively. The local repository is C:/Users/Chepuri/Documents/ChatGPT/sandhata, a sibling of BRIHASPATI and an independent Git repository. Always verify the working directory and origin before staging or pushing. Never run git add from the finance repository for this work.

## Initial publication commands

Open PowerShell and run these commands one at a time. The preparation step may already have created the local commit; git status will show whether there are changes. Authenticate through Git Credential Manager when prompted; do not paste tokens into chat.

```powershell
Set-Location -LiteralPath 'C:\Users\Chepuri\Documents\ChatGPT\sandhata'
git rev-parse --show-toplevel
git status --short
git remote -v
git log -1 --oneline
git ls-remote origin
git push -u origin main
```

The expected top-level path ends in sandhata and origin is https://github.com/hemach-git/sandhata.git. If authentication fails, resolve it in Git Credential Manager. If the repository is private, verify visibility in GitHub settings; do not make resume files public.

## If the remote already has an initial commit

Do not force push. Fetch, inspect and merge remote history, preserving the README or license that GitHub created. Resolve any conflicts in the specific files before continuing.

```powershell
git fetch origin
git log --oneline --all --decorate -8
git merge origin/main --allow-unrelated-histories
git status
git push -u origin main
```

This branch assumes the remote branch is main. If fetch shows another default branch, use that actual branch. A conflict requires resolving files, staging only those files and committing before push. Do not run the merge path unless the remote has history that needs integration.

## Subsequent collaboration

```powershell
git switch -c codex/core-workflow
git add src tests docs README.md
git diff --cached --stat
git commit -m "Implement core job comparison workflow"
git push -u origin codex/core-workflow
```

The example paths for implementation commits apply only once those directories exist. Review the staged content before every commit. Use a pull request for implementation changes and include behavior, validation and remaining limits. Avoid committing generated runtime logs, private resumes, SQLite files, environment files and document QA render images.

## Publication verification

After push, compare git rev-parse HEAD with git ls-remote origin refs/heads/main. Confirm the same commit and inspect the repository file list in GitHub. Record the SHA and URL in the release evidence. A local commit alone is not proof of publication. Never bypass rejected updates with force; inspect divergence first.

## Release workflow

Pin dependencies, run tests/evals, review the diff and create a version tag only after acceptance. Suggested first implementation tag is v0.1.0; the design package is not an implemented application release. Keep CI deterministic with synthetic data; a separate optional job handles live provider checks without exposing secrets in logs.
