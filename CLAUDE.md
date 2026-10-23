# CLAUDE.md — technical handoff (PitCrew, 2026-10-23)

Team project for the Austin Agentic AI Hackathon (Track 2: Autonomic Shop Floor & Predictive Maintenance).
**Challenge customer: NXP Semiconductors** — the demo fleet is semiconductor equipment (dicing saws, wire
bonders, test handlers, probers) at fab and assembly/test sites. Read README.md, then `idea.md` (the plan) and
docs/DECISIONS.md. Working style: understand intent, back choices with numbers, plain language, tests green
before every push.

## The shape

Three loops feed one priority queue of jobs (Cure > Prevention > Maintenance, then due date); an iron-tight
supply chain gets parts to the site first.

| Piece | What it does | Owner | Code |
|---|---|---|---|
| Maintenance | Component lifelines → scheduled jobs weeks ahead | Teammate | `contracts.py: lifeline_table` (placeholder) |
| Prevention | XGBoost failure risk per machine (AI4I features); ≥ 0.70 pulls the job forward, 0.40–0.70 adds predicted demand | Matthew | `failure_model/`, `contracts.py: failure_risk` |
| Cure | Error code "down" → top-priority job, part from nearest hub, email + escalation | Mudit | `contracts.py: ERROR_CODES`, `Plant.product_down` |
| Sourcing | Local → central → lateral → buy; cheapest-in-time vs fastest verified vendor; order-by; POs under policy | Mudit | `pitcrew/sourcing.py`, `Crew.sourcing()` |
| Internal fab | Machine-downtime status → in-house lead time | Hari | `machine_downtime_model/`, `contracts.py: fab_status` |

Hub network: one central hub (at the factory, most inventory) and local hubs near the sites.

## Run

```bash
pip install -r requirements.txt
python -m pytest -q                         # 22 tests
python scripts/run_demo.py                  # terminal demo
shiny run app/app.py --port 8000            # console (demo bar: 1 prevention, 2 cure, 3 fab, Reset)
python scripts/console_smoke.py --port 8000 # click-through over Shiny's websocket (needs the console running)
python scripts/run_sourcing.py              # the Sourcing agent once
```

Windows: the venv lives in `.venv`. If PowerShell blocks `Activate.ps1`, call `.venv\Scripts\python.exe` and
`.venv\Scripts\shiny.exe` directly. Workshop Linux box: `python3`; install `requirements-agent.txt` there
(shiny's libsass doesn't build on it).

Bedrock: `PITCREW_LLM=bedrock`, `PITCREW_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0` (on the
workshop allowlist; Sonnet 5.5 is not), `AWS_REGION`. Any model error falls back to the offline crew for that
step and says so. Deploy: docs/DEPLOY.md (AgentCore, container deploy).

## Map

- `pitcrew/world.py` — the only place agents touch state. Every tool records `{agent, tool, args, result}` in
  `World.trace`. Add a capability = add a method here + a `@tool` wrapper in `crew/strands_crew.py`.
  `predict_failure(record_udi)` exposes Matthew's model to the agents.
- `pitcrew/crew/` — `offline.py` (deterministic narration; the reference), `strands_crew.py` (Bedrock,
  GraphBuilder), `scripted_model.py` (fake Strands model for tests), `__init__.py` (`Crew` facade, fallback).
- `pitcrew/contracts.py` — what the console calls for each teammate's piece, and `Plant` (the demo fleet, hubs,
  inventory, the queue with stock allocation). Each machine's reading is a real AI4I record (`udi`);
  `Plant.product_drifts` swaps in record 162 (97% risk).
- `pitcrew/sourcing.py` — `Job` + `rank`; `Network` (hubs, sites, stock, verified vendor quotes); `fulfil`,
  `restock_local_hubs`, `central_plan`, `place_order`, `advance`. `demo_network()`/`demo_jobs()` match
  `docs/SIMULATION_PROMPT.md`; `tests/test_sourcing.py` pins the numbers.
- `failure_model/` — Matthew's model (`predict.py`, `train_model.py`, `failure_model.joblib`, AI4I CSV).
- `machine_downtime_model/` — Hari's model.
- `pitcrew/mill.py` — AI4I walls, Lift & Coast, mill economics (the VM-07 page).
- `pitcrew/ops.py` — parts room, technicians, work orders, POs, `POLICY`, `ALERT_POLICY`.
- `pitcrew/passport.py` — manual → asset passport (Grow, crew only).
- `app/app.py` — Shiny; one `World` and one `Plant` per session.
- `agentcore/agent.py` — AgentCore entrypoint (`action`: sourcing, predict, plan_mill, approve, grow).
- UI design canvas (teammate's): https://claude.ai/artifact/1S9Qbm5vMK6qFEgKWrNb3n

## Rules

- The only company named is the challenge customer, NXP. No other company's internal names, proprietary
  datasheets or internal values anywhere in the repo, its docs or commit messages.
- Numbers that aren't from a public source, a model or a tool are placeholders and are labelled as such.
- Screens and approval cards show tool numbers only. If a model-written number disagrees with a tool, the
  tool wins. The model chooses, explains and drafts; the math lives in tools.
- Secrets (AWS, SendGrid API key) never go in the repo; use env vars locally and Secrets Manager in AWS.
- Don't commit `Project.zip` or virtual environments (`.gitignore` covers them).

## Next steps, in value order

1. Deploy to AgentCore (docs/DEPLOY.md) and show the Sourcing agent + `predict` running there.
2. Replace the placeholder lifeline table with the teammate's pipeline output.
3. Feed Prevention from live readings instead of AI4I records; map failure modes to part numbers.
4. Unify `contracts.order_card` (console) with `sourcing.Network` (agent) so both read one inventory.
5. AgentCore Gateway + Policy for `World` tools; Bedrock Knowledge Base for `data/manuals/`.
