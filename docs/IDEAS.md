# Idea index — what is built, what is stretch, where to look

| Idea | One line | Status | See it |
|---|---|---|---|
| One priority queue | Cure > Prevention > Maintenance, stock allocated in queue order | **Built** | Priority queue |
| Prevention on a trained model | Matthew's XGBoost failure model scores every machine; ≥ 70% pulls its job forward | **Built** | Prevention |
| Cure | An error code that means "down" goes to the top; part pulled from the nearest hub; site emailed | **Built** (email simulated; SendGrid in AWS) | Cure, Alerts |
| Sourcing agent | Local → central → lateral → buy; cheapest-in-time vs fastest verified vendor; PO under policy | **Built** (offline + Bedrock + AgentCore) | Parts & sourcing |
| Internal fab | Hari's machine-downtime model sets in-house lead time; Sourcing switches to a vendor when it slips | **Built** | Internal fab |
| Lift & Coast (mill) | Derate inside the safe envelope to reach the next shift change | **Built** | VM-07 Lift & Coast |
| Policy gate | POs over $500 and every setpoint change wait for a person | **Built** (code); AgentCore Policy in AWS | approval cards, `ops.py` |
| Asset passport + onboarding | Manual → limits, signals, future sensor slots → human signs → agents start | **Built** (crew only) | `crew.grow`, AgentCore `grow` |
| Pitch simulation | Calm animated story of the queue and the hub network | Prompt written | `docs/SIMULATION_PROMPT.md` |
| A2A supplier negotiation | Sourcing talks to a supplier's own agent | Stretch: `agentcore/supplier_a2a.py` | — |
| Lifeline pipeline | Rated life per component from datasheets → scheduled jobs | Teammate's; placeholder table today | `contracts.py: lifeline_table` |
