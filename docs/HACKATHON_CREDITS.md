# CNTXT at OpenAI Build Week — Tel Aviv

CNTXT began as a live, working MVP built during the **OpenAI Build Week
Community Hackathon in Tel Aviv**. In a short build window, the team moved from
an architecture question to a demonstrable privacy gateway: retrieve local
enterprise context, transform protected values into stable placeholders, and
return useful context without sending those original values to an external
model.

## The idea that shaped the project

AI agents are becoming the interface to Slack, Drive, GitHub, databases and
other company knowledge. Authentication can decide whether an agent may call a
tool, but it does not automatically control what sensitive values appear in the
tool's result. CNTXT focuses on that missing layer.

```text
Enterprise connector → CNTXT policy and transformation → AI agent
                         ^ raw values stay local
```

Instead of deleting context, CNTXT changes values such as names, project
names, locations and amounts into deterministic placeholders. For example,
`Project Falcon` becomes `[PROJECT_1]` each time it appears in the same
project. The external model can reason about relationships, while the local
gateway retains the original-value mapping.

The resulting product direction is an **AI context firewall**: a policy and
privacy-transformation layer that can sit in front of MCP-connected enterprise
data sources. It complements access-control gateways rather than replacing
them.

## Hackathon context

The event recap shared with the team described a first Codex Community
hackathon in Tel Aviv, with **100+ participants across 30+ teams** building and
pitching working products in roughly six hours at Echo and Xsolla. CNTXT's
hackathon work centered on mapping the privacy-gateway concept and creating
the live demo that became this repository.

## Acknowledgments

- **OpenAI Build Week / OpenAI Codex** — the community hackathon setting and
  the coding environment used to develop, test, document and iterate on this
  MVP.
- [**Vlad Tansky**](https://www.linkedin.com/in/vlad-tansky/) and
  [**Eliezer Steinbock**](https://www.linkedin.com/in/elie222/) — organizers
  acknowledged by the team for bringing the Tel Aviv event together.
- **Echo** and **Xsolla** — event hosts.
- **CNTXT team** — [Liav Samiya](https://www.linkedin.com/in/liav-samiya/),
  [Daniel Armoni](https://www.linkedin.com/in/daniel-armoni/),
  [Gal Shitrit](https://www.linkedin.com/in/gal-shitrit-/), and
  [Naveh Talor](https://www.linkedin.com/in/naveh-talor-a2636810a/).

The team received OpenAI and Codex credits at the event, helping sustain the
project's continued iteration after the hackathon.

OpenAI, Codex, Echo, Xsolla and the named organizers are acknowledged for
their respective contributions. This repository is an independent team
project; these acknowledgments do not imply endorsement, affiliation, or
partnership by any named organization.

## Deck and further reading

- [CNTXT Pitch Deck — Light Theme & Timeline (PDF)](Cntxt-Pitch-Deck.pdf)
- [Architecture, current state and roadmap (Hebrew)](PROJECT_OVERVIEW.md)
- [Live-demo script](DEMO_SCRIPT.md)
