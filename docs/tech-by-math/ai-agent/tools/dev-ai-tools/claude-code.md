# Claude Code (VS Code) — Detailed Guide

Audience: Developers using VS Code who want a strong code-aware assistant with multi-file edits and chat.

Extension: "Claude – Code" (publisher: Anthropic). Requires an Anthropic account/sign-in in the extension.

## Quickstart (5–10 min)
1. VS Code > Extensions > search "Claude" (publisher Anthropic) > Install "Claude – Code".
2. Sign in when prompted (status item in the VS Code status bar or the Claude sidebar).
3. Open your repository folder, then:
   - Open the Claude sidebar (activity bar icon) and start a chat.
   - Select some code and run: Command Palette (Ctrl+Shift+P) > "Claude: Edit Selected Code".
   - Review the proposed diff and apply.

## Core concepts
- Chat: Ask questions with project awareness; use code blocks and references.
- Edit: Ask Claude to transform selections or files; review diffs before applying.
- Context: Claude can use the current file, open editors, and optionally the workspace (configurable).
- Models: Choose a model suited for your task. Typically, Sonnet for quality; Haiku for speed and low latency.

## Daily workflows
- Explain unfamiliar code: select a block > Right click > Claude > Explain.
- Refactor safely: select code > "Claude: Edit Selected Code"; ask for a specific change; review/apply the diff.
- Add tests: open the file under test; chat "Generate unit tests for edge cases, then explain rationale".
- Multi-file change: chat a plan, then ask for targeted edits per file; stage in Git and run tests.
- Documentation: "Create a README section summarizing this module and its public API with examples."
- Commit messages: paste the git diff and ask for a pragmatic message (imperative mood, scope, rationale).

## Prompt patterns that work well
- Request intent + constraints + verification:
  - "Refactor this function to be pure and side-effect free. Keep behavior identical. Add docstring and examples. Provide a unified diff only."
- Multi-file plan-then-apply:
  - "We will add a new configuration flag 'maxRetries'. 1) Update config schema. 2) Use flag in RetryPolicy. 3) Add unit tests. 4) Update README. Propose a file-by-file plan first, then produce diffs one file at a time after I confirm."
- Safer edits:
  - "Only modify the selected function. If other changes are needed, propose them separately."
- Test-first:
  - "Generate failing tests demonstrating the bug in FooParser when input contains UTF-16 surrogate pairs."

## Context management
- Keep prompts focused: point to a file or selection, or paste a small snippet with clear instructions.
- Use file mentions: say "In src/utils/date.ts ..." rather than pasting entire files.
- Control workspace context in settings to avoid sending large or sensitive files.
- Prefer selections for heavy code to keep token usage low and outputs precise.

## Editing with diffs (recommended)
1. Select the code to change or open the file and run "Claude: Edit Selected Code".
2. Describe the change precisely, including acceptance criteria.
3. Review the proposed diff in the side-by-side view; reject unrelated edits.
4. Apply, run tests, repeat iteratively.

Why diffs? They reduce hallucinations and make it easy to audit changes.

## Multi-file edits strategy
- Ask Claude to propose a plan and list affected files first.
- Apply edits incrementally per file; stage each change in Git.
- After each step: run unit tests or quick checks (type check, linter, build).
- If Claude proposes large sweeping edits, request smaller, isolated diffs.

## Settings to review (VS Code > Settings)
- Claude: Model Selection — choose Sonnet (quality) or Haiku (speed) based on task.
- Claude: Max Prompt Size — cap to avoid unbounded context usage on large repos.
- Claude: Enable Workspace Context — toggle whether unopened files can be referenced.
- Claude: File Include/Exclude Globs — limit which files are eligible for context.
- Claude: Telemetry — adjust data collection preferences if available in your build.

Note: Setting names vary by version; use Settings search for "Claude" to locate options.

## Privacy and security
- Treat prompts as data you are sharing with a third-party service; do not include secrets.
- Respect your organization’s data retention policy and select enterprise options if required.
- Use .env files and .gitignore; avoid pasting credentials, keys, internal URLs.
- Review diffs before applying; never apply changes you don’t understand.

## Advanced usage
- Cross-file reasoning: ask Claude to summarize relationships between modules before editing.
- API surface planning: ask for an API skeleton and examples; then implement iteratively.
- Codebase tours: "Create an overview of the data flow from controllers to persistence with file references."
- Migration assistant: "Propose steps to migrate from Mocha to Vitest. Provide a scriptable checklist."
- Performance hints: "Identify hotspots and add micro-benchmarks (Node: benchmark module, Python: timeit/pytest-benchmark)."

## Integrating with testing
- Ask to generate or update tests whenever behavior changes.
- Keep tests close to code (e.g., __tests__ or *.spec.ts) to simplify context.
- Use watch mode (e.g., jest --watch) and iterate with small diffs.
- Request property-based tests or fuzz cases for parsers and encoders.

## Handling large diffs and conflicts
- If the proposed change touches many files, ask for a minimal viable patch first.
- For merge conflicts, paste the conflict markers and ask Claude to resolve with justification.
- If edits feel noisy, explicitly instruct: "Only change X; do not reorder imports or reformat unless necessary."

## Common issues and fixes
- Token/size errors: reduce selection, disable workspace-wide context, or switch to a larger-context model when available.
- Low-quality suggestions: provide clearer constraints, acceptance criteria, or smaller scope.
- Network/proxy issues: configure VS Code proxy settings; sign out/in of the extension.
- Extension conflicts: disable overlapping AI extensions and compare behavior.

## Shortcuts and commands
- Claude: Open Chat (sidebar)
- Claude: Edit Selected Code (Command Palette)
- Claude: Explain Code (context menu)
- Keybindings can be set in Keyboard Shortcuts: search "Claude" and assign your preferred keys.

## Example end-to-end workflow
1. Goal: Add input validation to user registration.
2. Plan (chat): List fields, rules, error messages, and tests to add.
3. Edit (per file): Use "Edit Selected Code" on the validator and controller.
4. Tests: Ask for unit tests covering invalid inputs and boundary cases.
5. Docs: Ask for a README section summarizing validation rules.
6. Verify: Run tests, lint, typecheck; stage and commit with a Claude-drafted message.

## Tips for better results
- Use precise language: specify functions, files, and expected outputs.
- Prefer diffs and selections over free-form rewrites.
- Iterate: small changes + tests beat one massive change.
- Ask for explanations of non-obvious changes to build understanding.

## Links
- VS Code Marketplace: search for "Claude – Code (Anthropic)"
- Anthropic: https://www.anthropic.com/
