# CLAUDE.md — technical handoff (PitCrew, 2026-10-23)

Team project for the Austin Agentic AI Hackathon (Track 2: Autonomic Shop Floor & Predictive Maintenance).
**Challenge customer: NXP Semiconductors** — frame the pitch and demo around semiconductor manufacturing
(wafer fabs, fab/test equipment, spare parts); the solar-tower fleet in v0.1 is a simulated stand-in. Read `idea.md` first (the v0.2 plan), then README.md (what v0.1 built) and docs/DECISIONS.md. Working
style: understand intent, back choices with numbers, plain language, tests green before every push.

## Where the project is going (v0.2, see idea.md)

Three service loops feed one priority queue of jobs; an iron-tight supply chain gets parts to the site first.

| Piece | What it does | Owner |
|---|---|---|
| Maintenance | Component lifelines → scheduled jobs weeks ahead | Teammate (maintenance pipeline) |
| Prevention | Product A vs its peers (telemetry rate, error codes, performance) → re-rank the queue, divert parts | Matthew (failure-prediction model) |
| Cure | Error codes → top-priority job, SendGrid email, escalation | Team |
| Sourcing (outside) | Hub inventory + upcoming jobs + emergency buffer → when to order; cheapest vs fastest authorized vendor | Mudit |
| Internal fab (inside) | Factory machine downtime → production capacity and in-house part lead times | Hari |

Hub network: one central hub (next to the factory, most inventory) and local hubs near far-away job sites.

## Run

```bash
pip install -r requirements.txt
python -m pytest -q                         # 24 tests
python scripts/run_demo.py                  # terminal demo
shiny run app/app.py --port 8000            # console
python scripts/console_smoke.py --port 8000 # click-through over Shiny's websocket (needs the console running)
```

Windows: the venv lives in `.venv`. If PowerShell blocks `Activate.ps1`, call `.venv\Scripts\python.exe` and
`.venv\Scripts\shiny.exe` directly, or run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.

Bedrock instead of the offline crew: `PITCREW_LLM=bedrock`, `PITCREW_MODEL_ID=<model or inference profile>`,
`AWS_REGION`. Any model error falls back to the offline crew for that step and says so.

## Map

- `pitcrew/world.py` — the only place agents touch state. Every tool records `{agent, tool, args, result}` in
  `World.trace`. Add a capability = add a method here + a `@tool` wrapper in `crew/strands_crew.py`.
- `pitcrew/crew/` — `offline.py` (deterministic narration; the reference), `strands_crew.py` (Bedrock,
  GraphBuilder), `scripted_model.py` (fake Strands model for tests), `__init__.py` (`Crew` facade, fallback).
- `pitcrew/ops.py` — parts, quotes, technicians, work orders, POs, `POLICY` (POs over $500 need a human),
  `best_quote` (cheapest quote that arrives in time). **Starting point for Sourcing**: it has one parts room
  today; v0.2 needs hubs, demand from the job queue, a buffer, an order-by date, and cheapest + fastest.
- `pitcrew/mill.py` — AI4I walls, Lift & Coast, Monte Carlo, mill economics. **Starting point for Internal fab.**
- `pitcrew/tower.py` — `DriveModel` (all coefficients), `Fleet` simulation (48 ST-1 towers, 3 sites, lots
  A/B/C, demo towers 7/19/31/42 scripted), detectors, `rul_days`, `project`. Source of simulated telemetry
  for Prevention.
- `pitcrew/decide.py` — Park & Price; `TowerEconomics`; energy windows from the table.
- `pitcrew/kaizen.py`, `pitcrew/futures.py`, `pitcrew/passport.py` — v0.1 Improve and Grow loops (stretch in v0.2).
- `pitcrew/solar_face.py` + `scripts/export_energy_table.py` — two-wing field energy model; writes
  `data/tower_dallas_*`.
- `app/app.py` — Shiny; one shared `Fleet` (deterministic, read-only), one `World` per session.
- `agentcore/agent.py` — AgentCore entrypoint (`action`: plan_mill, plan_tower, approve, improve, grow).
- UI design canvas (teammate's): https://claude.ai/artifact/1S9Qbm5vMK6qFEgKWrNb3n

## Rules

- The only company the project is built for and named after is the challenge customer, NXP. No other
  company's internal names, proprietary datasheets or internal values anywhere in the repo, its docs or
  commit messages. The stand-in product is a generic "solar tower" (model ST-1; next generation ST-2).
- Numbers that aren't from a public source or a tool are placeholders and are labelled as such.
- Approval cards show tool numbers only. If a model-written number disagrees with a tool, the tool wins.
  The model chooses, explains and drafts; the math lives in tools.
- Secrets (AWS, SendGrid API key) never go in the repo; use env vars locally and Secrets Manager in AWS.
- Demo towers are scripted (`Fleet._inject_demo`); keep `tests/test_tower.py` green when retuning.

## Next steps, in value order

1. Sourcing: hub-aware inventory in `ops.py`, demand from a job queue, emergency buffer, order-by date,
   cheapest vs fastest vendor; tools in `world.py`; a Bedrock-backed Sourcing agent in `crew/`.
2. Agree the shared shapes with the team: `job` (idea.md §6) and `fab_forecast(part)` (idea.md §7b).
3. Prevention: peer-deviation score on `tower.py` telemetry; Cure: error-code table + SendGrid.
4. Fetch the real AI4I file in the workshop and rerun the tests (the replica's counts differ slightly).
5. AgentCore Gateway + Policy for `World` tools; Bedrock Knowledge Base for `data/manuals/`.
