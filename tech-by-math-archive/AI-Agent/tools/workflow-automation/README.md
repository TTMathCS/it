# Workflow Automation Tools for AI Agents

This section introduces n8n and popular alternatives for building workflow automations that integrate with AI agents. It covers when to use each tool, how they differ, and practical pointers to get started.

- Read about n8n in detail: [n8n.md](./n8n.md)
- Compare alternatives and choose the right tool: [alternatives.md](./alternatives.md)

Quick start:
- If you want an open-source, self-hostable visual workflow tool with strong extensibility, start with n8n.
- If you need enterprise-grade, code-first orchestration with complex retries and SLAs, consider Temporal or Airflow.
- For low-code SaaS integrations with many prebuilt connectors, check Zapier or Make.

Integration pattern with AI agents:
1. Agent invokes a webhook or queue to trigger an external workflow.
2. Workflow executes actions (APIs, DB, SaaS) with guardrails, retries, and approvals.
3. Workflow posts results back to the agent via callback, storage, or event bus.

See also: Agent development lifecycle (tool integration and observability) in the main README.
