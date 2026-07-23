# JARVIS

JARVIS is an open-source local control layer that gives Codex and other coding agents persistent projects, approval boundaries, execution tracking, and independent verification.

> **Public alpha:** JARVIS is developer-oriented pre-release software. Codex is implemented and live-tested. Claude Code support is implemented but has not yet been live-tested for this release.

[Start in five minutes](#five-minute-quick-start) · [Read the safety model](#safety-model) · [Troubleshoot](#troubleshooting)

> **New — JARVIS HUD:** this fork also ships a personal vision + voice assistant (camera, hand/face tracking, Iron-Man-style HUD, Claude Fable 5 brain, optional ElevenLabs voice). See [docs/JARVIS_HUD.md](docs/JARVIS_HUD.md).

Release version: `0.1.0-alpha.1` · intended tag: `v0.1.0-alpha.1`

Public repository: [https://github.com/adithyakupad/jarvis](https://github.com/adithyakupad/jarvis)

## What JARVIS does today

```text
Task → inspect → propose → approve → edit → verify → remember
```

- **Task:** You describe a coding outcome in a persistent project workspace.
- **Inspect:** The selected provider reads the repository to ground its plan; planning does not edit files.
- **Propose:** JARVIS shows the steps, expected file scope, risks, and completion evidence.
- **Approve:** You may Proceed with the exact current revision, Revise plan, or Cancel.
- **Edit:** Only after approval, the selected provider works inside the chosen repository.
- **Verify:** JARVIS observes repository changes and independently runs a supported project test command.
- **Remember:** Project state, proposal revisions, activity, changed paths, and validation evidence persist across restarts.

JARVIS owns project continuity, approval and execution state, repository evidence, validation, and chronological activity. Codex and Claude Code are replaceable planning and execution providers; they are not the source of JARVIS project truth.

## Who this alpha is for

This alpha is appropriate for developers and technical builders who:

- are comfortable with Git and a terminal;
- already use Codex or are willing to install and authenticate it;
- can review an agent's uncommitted changes; and
- will begin with a disposable or otherwise safe local repository.

It is not yet a desktop consumer application, fully autonomous personal assistant, cloud service, or replacement for reviewing code changes.

## Current provider status

| Provider | Planning and execution | Release verification | Unavailable behavior |
| --- | --- | --- | --- |
| Codex | Implemented | Live-tested | Explicit failure; no fallback |
| Claude Code | Adapter implemented | Not yet live-tested for this release | Explicit failure; no fallback |

JARVIS never silently changes the selected provider.

## Requirements

- macOS. Other operating systems may work, but they have not been release-verified.
- Git.
- Node.js 22.12 or newer and npm.
- Codex CLI installed and authenticated when using Codex.
- Claude Code installed and authenticated only when selecting Claude Code.
- An existing local Git repository that you trust and are willing to let an agent edit after approval.

Verify the tools you intend to use:

```bash
node --version
npm --version
git --version
codex --version
```

Authenticate Codex with `codex login`. If selecting Claude Code, verify `claude --version` and follow the authentication flow supported by your installed Claude Code release.

## Five-minute quick start

```bash
git clone https://github.com/adithyakupad/jarvis.git
cd jarvis
npm install
npm run jarvis
```

Keep the terminal open. JARVIS builds the production client, starts one Fastify process, and prints one authoritative localhost URL (normally `http://127.0.0.1:4173`). The frontend and API share that origin, and the server binds only to `127.0.0.1`; production startup does not depend on the Vite development proxy. Press `Ctrl+C` in this terminal to stop the owned instance cleanly.

## Add the first project

On first launch, JARVIS opens **Add an existing project**:

- **Project name:** A user-facing label shown in JARVIS, such as `Calculator` or `My App`.
- **Repository path:** The absolute path to an existing local Git repository. On macOS or Linux, enter the repository in a terminal and run `pwd` to obtain it—for example, `/Users/you/Projects/calculator` or `/home/you/projects/calculator`.
- **What are you building?:** A stable one- or two-sentence identity, such as `A TypeScript calculator library with automated tests.` This is not today's task.
- **Provider:** The coding agent JARVIS should use. Only a provider reported as ready can be selected.
- **Project context (optional):** Durable conventions, constraints, architecture, or goals, such as `Use TypeScript strict mode.` or `Do not modify generated files.`

**Do not put the immediate coding task in Project context. Submit the task after the workspace opens.**

> **Do not use the JARVIS source repository as your first execution target.** Start with a disposable repository or a repository whose changes you can review and recover through your normal Git workflow.

The repository does not need to be clean, but existing changes make attribution harder. Prefer a clean working tree for the first run.

## Run the first task

After **Open workspace**, enter the immediate task in **Task instruction**. A safe first example is:

```text
Add a multiply function that returns the product of two numbers and add an automated test. Follow existing conventions. Do not commit or push.
```

JARVIS asks the selected provider to inspect first. No edit occurs during planning. Review the proposal's steps, expected scope, risks, and completion evidence:

- **Proceed with revision N** seals and authorizes only the displayed current proposal revision, then begins execution.
- **Revise plan** asks for a new revision without approving the current one.
- **Add Context and Replan** supplies missing facts for this task; it does not replace durable Project context.
- **Cancel** ends the planning run before execution.

Do not Proceed unless the proposed scope and completion evidence are acceptable.

## Understand the result

**Run details** contains:

- current status and provider summary;
- **Validation**, JARVIS's independently observed test result;
- changed files and scope reconciliation;
- chronological activity;
- repository before/after evidence; and
- the approval record and sealed revision.

A provider saying it ran tests is not authoritative. The **Validation** section records whether JARVIS independently found and ran a supported test command and what it observed. A successful run normally leaves a dirty working tree because JARVIS does not automatically commit or push.

While planning or executing, the workspace shows real persisted activity and elapsed time. Timing diagnostics are available after completion. They are local-only and contain stage durations rather than prompts, credentials, or environment values.

Planning and Proceed acknowledge after their requested transition is persisted; long provider work then continues asynchronously in the local JARVIS process. SSE carries real chronological activity to the browser. JARVIS does not invent percentages or timer-based stages. One measured Codex smoke observed approximately 389 ms to accepted UI state, 20 seconds for planning, 377 ms for Proceed acknowledgement, 21 seconds for provider execution, and 239 ms for independent validation. These are examples, not latency guarantees.

## Review or undo changes

Inspect the target repository yourself:

```bash
git status
git diff
```

You are responsible for accepting, editing, reverting, or committing changes. Use your normal Git workflow and inspect paths carefully before undoing anything, especially when the repository had pre-existing changes. JARVIS does not reset, clean, stash, commit, or push the repository for you.

## Safety model

- The production alpha binds to localhost only.
- JARVIS resolves and records a canonical repository path.
- Planning is read-only; execution requires approval of one exact proposal revision.
- Provider selection is explicit and there is no silent fallback.
- Codex execution is repository-scoped with networking disabled; provider isolation differs by adapter, so this is not a claim of perfect sandboxing.
- JARVIS observes before/after repository evidence and does not automatically commit or push.
- JARVIS independently runs only the supported test command it discovers.
- Test scripts are trusted repository code and can perform arbitrary project-defined behavior. Only onboard repositories you trust.
- Models and providers can make mistakes. Review the proposal, changes, and validation evidence.

See [SECURITY.md](SECURITY.md) for the security policy.

## Data and privacy

By default JARVIS stores its SQLite state at `data/jarvis.db`. It persists project settings, canonical repository paths, provider session IDs, instructions, proposal revisions, context, approval decisions, normalized events, repository snapshots, results, validation evidence, inspection fingerprints, and timing events.

Use an isolated state directory:

```bash
JARVIS_DATA_DIR=/absolute/path/to/jarvis-state npm run jarvis
```

To remove one project, use **Edit project settings → Remove project**. This removes JARVIS-owned history, not repository files. To reset all default state, stop JARVIS and move or delete `data/jarvis.db` using your normal file-management workflow. If `JARVIS_DATA_DIR` was set, reset the database in that directory instead. Back it up first if its history matters.

JARVIS does not ship provider credentials. The selected provider may process repository content and prompts according to its own service, account, and privacy terms; JARVIS makes no broader privacy promise on the provider's behalf.

## Stopping and restarting

- Press `Ctrl+C` in the launch terminal to stop JARVIS.
- Restart from the JARVIS repository with `npm run jarvis` and reopen the printed URL.
- Completed and persisted history restores after restart.
- There is no durable background worker. Stopping during planning or execution interrupts in-process work, and repository files may already have changed.
- On startup, abandoned nonterminal work is marked interrupted with recovery guidance and is never rerun automatically.

`npm run jarvis` creates `<JARVIS_DATA_DIR>/jarvis.instance.lock` (or `data/jarvis.instance.lock` by default) containing safe process and compatibility metadata. Ctrl+C or SIGTERM closes Fastify and removes only the owned lock. A compatible duplicate invocation prints the existing URL and does not start another frontend/API pair. Dead locks are recovered. Malformed locks are preserved with a diagnostic suffix. A live PID is never trusted without probing `/api/health`, which protects against PID reuse.

Before hydrating projects or enabling actions, the browser verifies `/api/health` against the shared API schema and meaningful build identity. Older servers without that route are treated as incompatible. An incompatible JARVIS or unknown process occupying the port is reported with actionable guidance and is never terminated automatically.

Read-only planning inspection uses a conservative fingerprint of canonical path, Git HEAD, normalized status, and visible dirty or untracked contents. An unchanged fingerprint can reuse prior inspection findings for context-only replanning. Any observed repository-state change invalidates the cache. Execution always captures fresh before/after evidence, and validation detection always runs after edits; neither is served from inspection cache.

## Troubleshooting

Each entry gives the visible symptom, likely cause, and next action.

### Localhost page cannot be reached / JARVIS is not running

**Symptom:** The browser cannot open the printed URL. **Cause:** The launch process exited, is still building, or was stopped. **Next action:** Check the launch terminal for an error. From the repository run `npm run jarvis`, wait for the URL, keep the terminal open, and open that exact URL.

### A different JARVIS version is already running

**Symptom:** Startup reports another instance or an incompatible build. **Cause:** A prior JARVIS process with a different schema, version, or build is still running. **Next action:** Stop its terminal with `Ctrl+C`, run `npm run jarvis` again, and reload. Use the PID shown by JARVIS only when the old terminal cannot be found; do not kill unrelated processes blindly.

### Port already occupied

**Symptom:** Startup reports that `4173` or an API port is in use. **Cause:** Another process owns the local port. **Next action:** Stop the known process using that port, then rerun `npm run jarvis`. Do not terminate an unknown process without identifying it.

### API unavailable or incompatible

**Symptom:** The page says JARVIS could not load or requests fail. **Cause:** The local API did not start, stopped, or does not match the browser build. **Next action:** Stop JARVIS, rerun `npm run jarvis` so the client and API rebuild together, then reload. Save startup output if it persists.

### Codex unavailable or authentication required

**Symptom:** Codex is not installed, unavailable, or cannot be selected. **Cause:** The `codex` executable is missing from the launch environment or is not authenticated. **Next action:** Run `codex --version`, then `codex login`; restart JARVIS and confirm Codex shows **Ready**.

### Claude Code unavailable

**Symptom:** Claude Code is disabled or reports unavailable. **Cause:** The `claude` executable is absent or authentication could not be confirmed. **Next action:** Verify `claude --version`, complete the authentication flow for your installed release, restart JARVIS, and remember that this adapter is not yet live-tested for the current release.

### Repository path does not exist or is unreadable

**Symptom:** Setup rejects the path. **Cause:** It is relative, misspelled, not a directory, or inaccessible to your user. **Next action:** In the repository run `pwd`, paste the complete absolute path, and confirm your user can list its contents.

### Repository is not Git-based

**Symptom:** Path validation says the directory is not a Git repository. **Cause:** The selected directory has no Git metadata or is the wrong level. **Next action:** Choose the actual Git repository root. Do not initialize or modify an important directory merely to bypass the warning.

### Planning appears slow

**Symptom:** The UI remains in inspection/planning. **Cause:** Provider startup, repository inspection, and model work can take time. **Next action:** Follow the persisted activity stages and elapsed time, keep JARVIS running, and avoid submitting the action repeatedly. If it never completes, record sanitized output and report a bug.

### Execution was interrupted or failed

**Symptom:** JARVIS stopped, reports failure, or does not show a completed result. **Cause:** The provider, process, or application ended after execution may have begun. **Next action:** Assume files may have changed. In the target repository run `git status` and `git diff`, review Run details and terminal output, then restart JARVIS. Do not blindly Proceed again.

### Tests failed

**Symptom:** Validation reports failure or timeout. **Cause:** JARVIS ran the repository's supported test script and observed a non-passing result. **Next action:** Read the Validation output, inspect `git diff`, and decide whether to revise the task, fix the change manually, or revert it through your normal Git workflow. Provider edits remain in the repository.

### No supported automated tests were found

**Symptom:** Validation says automated tests were not run. **Cause:** The repository lacks a supported non-placeholder `package.json` test script or uses an unsupported project type. **Next action:** Review the changes manually and run the project's documented validation yourself. Do not interpret this state as a test pass.

### Browser shows stale content

**Symptom:** The browser does not reflect the latest persisted run. **Cause:** The event connection or cached client state may be stale. **Next action:** Reload the printed localhost URL. If the state still differs from the terminal or repository, restart JARVIS and report the discrepancy with sanitized evidence.

## Alpha limitations

- Developer-oriented terminal installation; no desktop wrapper.
- Local machine only; no cloud hosting or cross-device synchronization.
- Release-verified on macOS only; Linux and Windows have not been release-tested.
- Independent validation is limited to supported non-placeholder JavaScript/TypeScript `package.json` test scripts.
- Claude Code is not yet live-tested for this release.
- No automatic rollback, commit, push, or general-purpose recovery; users must review all changes.
- No durable background worker; restart interrupts active in-process work.
- Chronological activity can expose technical provider and repository event details.
- No voice or general personal memory.
- No reliable mid-execution cancellation guarantee for every provider.
- Models may misunderstand tasks or produce incorrect changes.

## Roadmap

Future work may include broader provider verification, validation support, packaging, and interface refinement. See [docs/ROADMAP.md](docs/ROADMAP.md); current behavior takes precedence over future direction.

## Development

For contributors, run the API and browser development server in separate terminals:

```bash
npm install
npm run dev:api
```

```bash
npm run dev
```

For deterministic UI-only fixture data, use `VITE_JARVIS_DATA_MODE=mock npm run dev`. Production mode never silently falls back to mock data.

Run deterministic validation with:

```bash
npm test
npm run typecheck
npm run build
```

The temporary Python baseline remains until TypeScript parity is verified.

## Contributing and support

- [Contributing guide](CONTRIBUTING.md)
- [Security policy](SECURITY.md)
- [Bug report template](.github/ISSUE_TEMPLATE/bug_report.yml)
- [Product requirements](docs/PRD.md)
- [New-user audit](docs/NEW_USER_AUDIT.md)
- [License](LICENSE)

A useful bug report includes operating system, Node version, JARVIS version or commit, selected provider and version, sanitized startup output, exact error category, reproduction steps, sanitized logs, and whether the target repository was clean before execution.

Never post credentials, tokens, private source code, personal filesystem details, or an entire JARVIS database.
