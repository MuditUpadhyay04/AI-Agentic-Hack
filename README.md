# PitCrew — Prevention · Cure · Maintenance on an iron-tight supply chain

An agent crew for the Austin Agentic AI Hackathon, Track 2 (Autonomic Shop Floor & Predictive Maintenance),
built for **NXP Semiconductors**. One priority queue holds every task for the equipment fleet; three loops feed
it and a hub network supports all three.

| Loop | What feeds the queue | Owner | Where to see it |
|---|---|---|---|
| **Cure** | An error code that means "down": top of the queue, part pulled from the nearest hub, site emailed | Mudit | `Cure`, `Alerts` |
| **Prevention** | Matthew's XGBoost failure model scores every machine's reading; ≥ 70% risk pulls its job forward | Matthew | `Prevention` |
| **Maintenance** | Lifelines (rated life per component) schedule routine jobs weeks ahead | teammate | `Priority queue` |
| **Sourcing** | Local hub → central hub → another local hub → buy the cheapest verified vendor that arrives in time | Mudit | `Parts & sourcing` |
| **Internal fab** | Hari's machine-downtime model sets in-house lead times | Hari | `Internal fab` |

## Quick start (no AWS needed)

```bash
pip install -r requirements.txt          # Python 3.10+
python -m pytest -q                      # 22 tests
python scripts/run_demo.py               # mill crew, Prevention, Sourcing, Grow in the terminal
shiny run app/app.py --port 8000         # the console -> http://localhost:8000 (demo bar: buttons 1–3)
```

The crew runs **offline** by default: same tools, same numbers, narration written from the tool results.
On Bedrock (see [docs/BEDROCK.md](docs/BEDROCK.md)):

```bash
export PITCREW_LLM=bedrock
export PITCREW_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0
python scripts/run_sourcing.py
```

Deploying to Bedrock AgentCore Runtime: [docs/DEPLOY.md](docs/DEPLOY.md). Any model error falls back to the
offline crew for that step and says so on screen.

## How the numbers are made

- **Prevention:** `failure_model/` holds Matthew's model (XGBoost, trained on AI4I 2020: type, air and process
  temperature, spindle speed, torque, tool wear). Each machine's reading is a real AI4I record; the demo's drift
  is record 162 (overstrain), which the model scores at 97%. `pitcrew/contracts.py: failure_risk`.
- **Internal fab:** `machine_downtime_model/` holds Hari's model (NORMAL / CAUTION / FAILURE WARNING).
- **Sourcing:** `pitcrew/sourcing.py` — the ladder, local restock, need-by and order-by dates, cheapest-in-time
  vs fastest vendor, POs under policy. Its demo data matches `docs/SIMULATION_PROMPT.md`.
- **Mill walls (VM-07):** AI4I 2020's published failure rules. `pitcrew/mill.py`.
- **Placeholders:** the fleet names, hubs, part numbers, vendors, prices and lifelines.

## AWS

| Piece | Service | File |
|---|---|---|
| Agents | Strands Agents on Amazon Bedrock (Sourcing agent; mill crew as a Graph) | `pitcrew/crew/strands_crew.py` |
| Runtime | Bedrock AgentCore Runtime (`sourcing`, `predict`, `plan_mill`, `approve`, `grow`) | `agentcore/agent.py` |
| Tools | `World` tools, every call traced | `pitcrew/world.py` |
| Guardrails | POs over $500 and every setpoint change need a person (AgentCore Policy / Cedar; in code offline) | `pitcrew/ops.py` |
| Suppliers | A2A supplier agent (stretch) | `agentcore/supplier_a2a.py` |

## Repository

```
pitcrew/          sourcing.py (Sourcing), contracts.py (queue, Prevention, Cure, fab, order card), mill.py,
                  ops.py (parts, POs, roster, policy), passport.py, world.py (tools), viz.py
pitcrew/crew/     offline.py, strands_crew.py (Bedrock), scripted_model.py (tests), __init__.py (Crew facade)
failure_model/    Matthew's XGBoost failure model + AI4I data
machine_downtime_model/   Hari's machine-downtime model
app/              Shiny operator console
agentcore/        AgentCore entrypoint, A2A supplier agent
scripts/          run_demo, run_sourcing, console_smoke, invoke_agentcore, fetch_data
docs/             BEDROCK, DEPLOY, SIMULATION_PROMPT, DEMO_SCRIPT, DECISIONS, DATASETS, IDEAS, PRFAQ
tests/            pytest suite
```

Hackathon prototype, not a control system: setpoint "writes" and purchase orders change simulated state only.
