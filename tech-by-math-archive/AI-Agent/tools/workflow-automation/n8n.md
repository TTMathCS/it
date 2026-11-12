# n8n for AI Agents

n8n is an open-source, self-hostable workflow automation tool with a visual editor and a rich node ecosystem. It’s useful for orchestrating multi-step actions that your AI agents trigger or respond to, with retries, approvals, and integrations to SaaS and internal services.

## When to use n8n
- You want a visual, low-code workflow builder that is extensible with custom nodes.
- You need to host it yourself (data residency, cost control) or start with the hosted cloud.
- You need webhooks, schedules, queues, and robust credentials management for many services.
- You want human-in-the-loop steps (e.g., approvals) and error handling policies.

## Install and setup
- Cloud: Create a workspace at https://n8n.io and start building flows.
- Docker (self-host):
  ```yaml
  version: '3'
  services:
    n8n:
      image: n8nio/n8n:latest
      ports:
        - "5678:5678"
      environment:
        - N8N_HOST=localhost
        - N8N_PORT=5678
        - N8N_PROTOCOL=http
      volumes:
        - ./n8n_data:/home/node/.n8n
  ```
- Credentials: Add API keys/secrets in n8n Credentials. Use environment variables or a secrets manager for production.

## Core concepts for AI-agent integrations
- Triggers: webhooks, schedules, queues (e.g., RabbitMQ, Kafka), or polling SaaS.
- Nodes: HTTP Request, Function (JS), Database, Email/Chat, Storage, AI providers, custom nodes.
- Execution: parallel branches, error branches, retries, timeouts.
- Human-in-the-loop: pause for approval via email/Slack and resume on callback.
- Observability: execution logs, error runs, data mapping; add your own tracing IDs.

## Integration patterns
1. Agent → n8n via Webhook
   - The agent calls an n8n webhook with task payload.
   - n8n performs actions (API calls, DB ops), handles retries, and returns a result or callback URL.
2. n8n → Agent callback
   - n8n posts results to an agent endpoint or a message bus (Kafka, SQS) the agent consumes.
3. Fire-and-forget with status polling
   - Agent submits a job ID; later polls a status endpoint exposed by n8n or a backing queue.

## Example: Ticket triage workflow
- Trigger: Webhook receives {ticket_id, customer_id, issue_summary}.
- Steps:
  1) Fetch customer and billing context (HTTP/DB).
  2) Use LLM/Rules to classify severity and suggest actions.
  3) If low-risk, execute remediation via API; else request approval in Slack/Email.
  4) Log results to CRM and send a status callback to the agent.
- Error handling: retry transient API failures; escalate to a human after N retries.

## Pros
- Open-source, self-hostable, strong node ecosystem, visual builder.
- Flexible with custom JavaScript function nodes and community nodes.
- Good for rapid iteration and operational workflows around agents.

## Cons
- Not a replacement for heavy data engineering/ML pipelines.
- Long-running, mission-critical orchestrations might need code-first engines.

## Security and governance tips
- Scope credentials per workflow; avoid sharing global secrets widely.
- Store PII minimally; redact logs; set execution timeouts and rate limits.
- Use approvals and role-based access for privileged actions.

## Useful links
- n8n Docs: https://docs.n8n.io
- Docker image: https://hub.docker.com/r/n8nio/n8n
- Community: https://community.n8n.io
