# Developer AI Tools: Practical Guides

This folder provides practical, security-minded guides for using leading AI assistants in software development.

Included tools:
- JetBrains AI (IntelliJ/JetBrains IDEs)
- Genie (VS Code extension)
- ChatGPT (web + API assisted workflows)
- GitHub Copilot (VS Code/JetBrains/Neovim)
- Claude Code (VS Code) — detailed guide

How to use these docs:
- Start with the tool you already have access to.
- Use the “Quickstart” sections for a 10-minute setup.
- Reference the “Daily workflows” and “Prompt patterns” as you work.
- Review “Security & compliance” before enabling repository-wide features.

Guides:
- JetBrains AI: ./jetbrains-ai.md
- Genie: ./genie.md
- ChatGPT: ./chatgpt.md
- GitHub Copilot: ./copilot.md
- Claude Code (detailed): ./claude-code.md

Comparison at a glance:
- IDE-native tight integration: JetBrains AI, Copilot, Claude Code (VS Code)
- Best conversational planning: ChatGPT, Claude (via web) + Claude Code in-editor
- Strong offline/privacy posture: Depends on enterprise plans and self-hosting options
- Best code refactor UX in VS Code: Claude Code and Copilot Chat

Notes:
- These tools are complementary. Many teams pair: Copilot (inline) + Claude Code (chat + workspace edits) + ChatGPT (planning/research).
- Prefer small, iterative changes with diff previews and tests.
