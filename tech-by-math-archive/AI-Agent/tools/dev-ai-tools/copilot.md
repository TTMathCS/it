# GitHub Copilot (VS Code, JetBrains, Neovim)

Audience: Developers who want strong inline code completion with optional chat.

Extensions:
- VS Code: "GitHub Copilot" and "GitHub Copilot Chat"
- JetBrains IDEs: "GitHub Copilot"
- Neovim: github/copilot.vim

## Quickstart (5–10 min)
1. Ensure you have an active Copilot subscription (personal or enterprise).
2. VS Code: Install GitHub Copilot + Copilot Chat from the Marketplace. Sign in to GitHub when prompted.
3. JetBrains: Settings > Plugins > Marketplace > GitHub Copilot > Install. Sign in.
4. Start typing in code to see inline suggestions. Accept with Tab (VS Code default).
5. Open Copilot Chat in the sidebar for conversational help.

## Key features
- Inline code completion (functions, unit tests, comments-to-code)
- Chat for explanations, refactors, and suggestions with repo context (enterprise enhances context)
- Slash commands and Quick Chat in VS Code
- Ghost text previews with accept/next/previous controls

## Daily workflows
- Comment-driven coding: Write a terse comment describing intent, accept inline suggestion, then refine.
- Test-first: Write a test name and signature, let Copilot draft the body, then adjust.
- Boilerplate reduction: Generate repetitive code patterns (mappers, DTOs, builders).
- Shell/regex helpers: Ask Copilot Chat to draft commands and explain them.

## Prompt patterns (Chat)
- "Given this diff, identify missing tests and propose a minimal test patch."
- "Refactor this function for clarity; keep behavior identical and add docstring."
- "Summarize this file’s responsibilities and list potential edge cases."

## Configuration tips
- VS Code Settings > Copilot:
  - Enable per-language toggles; disable in files where it’s noisy (e.g., lockfiles, JSON schemas).
  - Block suggestions that match public code: enable "Filter suggestions" (enterprise policies may apply).
  - Keybindings: configure accept word/line to control granularity.
- JetBrains: Settings > Tools > GitHub Copilot: tune suggestion display and triggers.

## Security & compliance
- Review GitHub Copilot data usage and suggestion filtering settings.
- Avoid accepting suggestions containing secrets or license-problematic snippets.
- Prefer enterprise controls (SSO, policy, telemetry) where available.

## Troubleshooting
- Low-quality or missing suggestions: ensure the file is recognized (language mode), check network/auth.
- Competing completion engines: temporarily disable other AI extensions to compare.
- Rate limiting: wait/retry or reduce rapid cursor movements that trigger many requests.
