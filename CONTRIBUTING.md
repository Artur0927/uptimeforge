# Contributing

Use focused Conventional Commits and reviewed feature-branch Pull Requests.
Preserve the owner's existing Git author configuration and all unrelated work.
Do not force-push or rewrite published history to remove ordinary documentation.
Do not add automated AI author/co-author attribution unless a platform or policy
requires it; never fabricate identities or remove mandatory attribution.

Before every commit, inspect `git diff --cached --name-status`,
`git diff --cached --check` and the complete staged diff. Exclude secrets,
Terraform state and temporary agent artifacts: handoffs, session summaries,
context-transfer files, audit/review notes and temporary diff/patch reports.
Keep temporary work outside the repository. `.gitignore` does not untrack files;
remove tracked temporary artifacts through focused normal commits.

Preserve useful engineering documentation, including READMEs, architecture,
developer setup, Terraform documentation and deployment/recovery runbooks.
Executable CI workflows are source code; the OIDC diagnostics workflow must not
be removed merely because its former handoff Markdown was temporary.

Do not merge PRs or change live infrastructure, credentials, organizations or
billing without the corresponding explicit approval. Terraform IAM creation and
Docker Host profile migration are separate review stages.
