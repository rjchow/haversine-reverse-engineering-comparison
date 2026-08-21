# Sandboxed benchmark-run methodology

This project uses a filesystem-isolated Pi session for a new benchmark run so
that it cannot inspect an earlier run's deliverables, logs, or credentials.
The isolation protects comparison independence while leaving normal research
tools, package installation, temporary files, and public-network access
available.

## Run layout

1. Create a fresh workspace outside the comparison repository.
2. Copy only the canonical `PROMPT.md` brief into that workspace as `brief.md`.
3. Give Pi a new, workspace-local session directory and temporary directory.
4. Start Pi in a dedicated `tmux` session with the common user prompt:

   ```text
   read the brief and start work. log your progress as you go along so that we can review the progress and track the outstanding task and so that you don't lose progress when context is compacted
   ```

5. Disable Pi extension, skill, and project-context discovery. The run still
   has Pi's built-in tools and may install or use ordinary research tools.

## Filesystem boundary

On macOS, the launcher uses `sandbox-exec` with an allow-by-default profile and
explicit deny rules for:

- the comparison repository and all earlier benchmark workspaces;
- Pi and Codex session-history directories;
- GitHub CLI, SSH, Git credential, and netrc stores.

The live profile necessarily contains machine-specific absolute paths, so it is
kept in the isolated run workspace and not published here. Its normalized form
is:

```scheme
(version 1)
(allow default)

(deny file-read*  (subpath "<comparison-root>"))
(deny file-write* (subpath "<comparison-root>"))
(deny file-read*  (subpath "<earlier-run-workspace>"))
(deny file-write* (subpath "<earlier-run-workspace>"))
(deny file-read*  (subpath "<pi-session-history>"))
(deny file-write* (subpath "<pi-session-history>"))
(deny file-read*  (subpath "<codex-session-history>"))
(deny file-write* (subpath "<codex-session-history>"))
(deny file-read*  (subpath "<github-credentials>"))
(deny file-write* (subpath "<github-credentials>"))
(deny file-read*  (subpath "<ssh-credentials>"))
(deny file-write* (subpath "<ssh-credentials>"))
```

The model therefore has access to its own workspace and permitted external
research sources, but cannot read prior-agent output, raw histories, or local
publishing credentials.

## Preflight checks

Before launching, verify that the sandbox:

- can read `brief.md` and create a file in its own workspace;
- rejects reads of each prior-run workspace and the comparison repository;
- rejects reads of Pi/Codex session histories and local GitHub credentials;
- can execute Pi, ordinary tool installers, and a network client.

These checks establish the intended boundary but do not make the benchmark a
model-only evaluation: the Pi harness, its built-in prompts, available tools,
and public sources remain part of the run environment.
