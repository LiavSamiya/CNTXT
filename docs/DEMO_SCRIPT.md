# ShieldAI judge demo — 90 seconds

1. Open the local dashboard and select **John Carter / Engineer**.
2. Leave **Defense Program Protection** selected and run
   `shieldai.search_slack_messages` with `latest Falcon discussion`.
3. Point out the timeline: identity, authorization, local policy, then a safe
   MCP result.
4. Compare the local-only raw connector result with the green safe context.
   Explain that the model sees only `[PROJECT_1]`, `[PERSON_1]`, and similar
   placeholders, never the actual values.
5. Show the local placeholder map and the rehydrated response. Emphasize that
   the map is not in the MCP response and is never supplied to the model.
6. Switch to **Maya Chen / Finance Analyst** and run the same engineering
   search. The gateway blocks it before a connector result is returned.
7. Open the audit trail. It records the actor, tool, policy decision, entity
   count, and latency — without preserving raw connector content.

Closing line: **"ShieldAI does not ask enterprises to trust every AI connector.
It makes policy enforcement the only path between agents and internal data."**

