# JetBrains AI (IntelliJ-based IDEs)

Audience: Developers using IntelliJ IDEA, PyCharm, WebStorm, GoLand, etc.

## Quickstart (5–10 min)
1. Update IDE to the latest version.
2. JetBrains AI plugin is bundled in recent IDEs. If missing: Settings > Plugins > Marketplace > "JetBrains AI" > Install.
3. Sign in to your JetBrains account and enable JetBrains AI features (status bar or Tools > JetBrains AI).
4. Open a project and try:
   - Ask AI: Tools > AI Assistant > Ask
   - Inline code completion: start typing in editor
   - Generate docs: select code > AI Actions > Explain or Document

## Key features
- Chat in IDE with project context
- Inline code completion and refactors
- Code explanations and documentation generation
- Commit message generation and code review assistance
- Test generation and quick-fix suggestions

## Daily workflows
- Draft functions/tests: Type a signature and accept inline suggestions.
- Explain unfamiliar code: Select range > AI Actions > Explain.
- Refactor with safety: Request transformation in chat, review suggested diff, run tests.
- Write commit messages: VCS > Commit > Generate message.

## Prompt patterns
- "Given this method, generate unit tests with edge cases: null input, large input, and error paths."
- "Explain performance bottlenecks and propose O(n log n) alternative."
- "Refactor to pure function, keep behavior identical; add docstring and examples."

## Configuration tips
- Settings > Tools > AI Assistant:
  - Enable/disable features per project.
  - Control context sharing and telemetry.
- Respect .gitignore: avoid sharing secrets; consider masking files via "Contexts" settings if available.

## Security & compliance
- Review JetBrains AI data policy and model providers used in your region.
- Exclude secrets and private keys from prompts. Use secret scanners in CI.

## Troubleshooting
- If suggestions are low quality or not showing: check network/proxy, ensure project indexing is complete.
- Conflicts with other completion plugins (e.g., Copilot): temporarily disable one to compare.
