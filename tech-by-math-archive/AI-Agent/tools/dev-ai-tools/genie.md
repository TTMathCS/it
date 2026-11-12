# Genie (VS Code ChatGPT Extension)

Audience: Developers using VS Code who want a lightweight chat/command palette assistant.

Extension: "ChatGPT - Genie AI" (publisher: Genie AI). Install from VS Code Marketplace.

## Quickstart (5–10 min)
1. VS Code > Extensions > search "Genie AI" (ID: genieai.chatgpt-vscode) > Install.
2. Open Command Palette (Ctrl+Shift+P) > "Genie: Set API Key" and paste your OpenAI API key.
3. Open Genie panel (activity bar) or use Command Palette commands:
   - "Genie: Ask"
   - "Genie: Explain Selection"
   - "Genie: Fix/Refactor Selection"

## Key features
- In-editor chat with context from the active file/selection.
- Explain/refactor/fix selected code commands.
- Supports model selection via settings (varies by version).

## Daily workflows
- Highlight code > Right click > Genie > Explain or Refactor.
- Use chat to plan changes and paste diffs back into files.
- Generate tests by selecting a function and running "Genie: Generate Tests" if available, or prompt in chat.

## Prompt patterns
- "Explain why this function is O(n^2) and refactor to O(n log n). Provide a diff."
- "Generate Jest tests for edge cases: empty input, large arrays, invalid args."
- "Summarize this file and list risky areas to change."

## Configuration tips
- Settings > Extensions > Genie: set model, max tokens, temperature.
- Disable sending large files if on limited quotas; prefer selections.

## Security & compliance
- Store API keys in VS Code secret storage.
- Avoid sending secrets; use .env and .gitignore; redact before prompts.

## Troubleshooting
- If API errors occur, verify key and model availability/limits.
- Conflicts with other chat extensions: disable others temporarily.
