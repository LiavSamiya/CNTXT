# ShieldAI — script for a 90-second demo

## Before the demo

1. Start `backend/app.py` and open `http://127.0.0.1:8787`.
2. Keep the **Overview** screen open.
3. For the reliable hackathon flow, use the Slack demo source and the query
   `latest Falcon discussion`.
4. Do not present Slack, GitHub or the local response as a live external
   integration. They are demo data unless Google Drive OAuth was configured.

## Suggested narrative

### 0–15 seconds — the problem

> “Companies want employees to use AI with Slack, Drive and GitHub, but they
> cannot send project names, people, secrets and financial information to an
> external model. Blocking AI completely kills productivity; deleting all
> sensitive text kills context.”

### 15–35 seconds — the architecture

Open **MCP connections**.

> “Instead of connecting the AI client directly to a connector, every tool
> call enters ShieldAI first. ShieldAI retrieves the context locally, applies
> the company policy, and only then returns a safe result through MCP.”

Point to the diagram:

```text
AI client → ShieldAI policy gateway → connector
```

### 35–60 seconds — the privacy transformation

Open **Live firewall**, keep **Slack MCP · search messages** selected, and
click **Protect context**.

> “The left side is raw organizational context and never leaves the local
> boundary. The center applies local dictionary and pattern detection. The
> right side is the only payload an AI client receives.”

Call out one or two replacements:

```text
Project Falcon              → [PROJECT_1]
John Smith                  → [PERSON_1]
North Ridge Test Facility   → [LOCATION_1]
```

> “The model still understands relationships and can reason about the project,
> but it never receives the real values.”

### 60–75 seconds — deterministic memory

Open **Project memory**.

> “Mappings remain locally inside the gateway. When the same project appears
> again, it receives the same placeholder, so follow-up reasoning stays
> consistent without revealing the original data.”

### 75–90 seconds — policy control

Open **Policies**. Toggle one protected category or add a custom term, for
example `Falcon Database` as `DATABASE`.

> “The organization does not need to change the model. It simply decides what
> the model must never see. The policy is applied on every protected response.”

## Closing line

> **“ShieldAI is the local privacy transformation layer for MCP: the model gets
> useful context, while the organization keeps its sensitive values.”**

## Honest implementation note

The current MVP demonstrates the full transformation path. Slack and GitHub
use safe fake data; Google Drive can be connected as a real read-only OAuth
source. SSO/RBAC, generic external MCP proxying, encrypted memory and a real
LLM provider are next-stage product work.
