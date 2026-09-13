# GitHub MCP Quick Guide — Retired in v27.0.1

This historical page is retained so old links remain readable. V27.0.1 does
not ship an MCP server, a web API, a token file, or a remote control plane.
There is no `.vscode/mcp.json` setup required for the application.

Use the current repository automation instead:

- run `LOOFI_IPC_MODE=disabled QT_QPA_PLATFORM=offscreen just verify` locally;
- use `.github/workflows/ci.yml` for pull-request validation;
- use the GitHub CodeQL default setup for Python and GitHub Actions scanning;
- use `.github/workflows/auto-release.yml` for the exact master/tag release;
- use `.github/workflows/publish-wiki.yml` for tracked wiki publication.

Never put a GitHub token, password, or other secret in the repository, an
issue, a pull request, or application state. The current security model is
documented in [the Action Center security guide](../wiki/Security-Model.md).
