# ChatGPT (Web + API Workflows)

Audience: Developers using ChatGPT for planning, code review, prototyping, and research.

## Quickstart (5–10 min)
1. Open https://chat.openai.com (or your enterprise domain) and sign in.
2. Create a workspace for your team if available; enable code interpreter if your plan supports it.
3. Create a custom instruction profile with your stack, coding style, and constraints.

## Typical use cases
- Design: draft architecture, API designs, data models, ADRs.
- Code review: paste diffs for summary and risk spotting.
- Refactoring plans: get a step-by-step sequence before editing in IDE.
- Test planning: enumerate unit/integration/e2e cases before writing tests.
- Research: compare libraries, outline migration steps, generate checklists.

## Prompt patterns
- System framing: "You are a senior engineer focused on correctness, tests, and security."
- Code review: "Review this diff. Identify defects, risky changes, and missing tests. Then propose focused improvements."
- Migration: "Given this package.json and tsconfig, outline steps to migrate to ESLint v9 with typescript-eslint."
- Benchmark plan: "Propose a micro-benchmark to compare these two functions (inputs, data sizes, metrics)."

## Copy/paste discipline
- Prefer minimal reproductions and specific files over whole repos.
- Redact secrets and internal URLs.
- Use GitHub Gists or playgrounds for sharable snippets if needed.

## With the API
- Use the OpenAI SDK from Node/Python for scripted helpers (lint rule generators, doc writers).
- Always log prompts/responses for audit and reproducibility; store in a local file or database.
- Implement retry with exponential backoff, and a token budget per request.

## Security & compliance
- Verify your org’s data retention settings and model access.
- Avoid pasting private keys, tokens, or customer data.
- Prefer enterprise features for data controls and SSO.

## Troubleshooting
- Hallucinations: ask for citations, request diffs not complete files, verify with tests.
- Rate limits: batch requests, add caching, or upgrade your plan.
