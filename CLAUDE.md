# CLAUDE.md — technical handoff (PitCrew v0.1.0, 2026-10-23)

Read README.md first, then docs/DECISIONS.md. Owner: founder at Janta Power (DFW), building for the Austin
Agentic AI Hackathon (Track 2). Same working style as the Shadow Calculator: understand intent, back
choices with numbers, plain language, tests green before every zip.

## Run

```bash
pip install -r requirements.txt
python -m pytest -q                         # 25 tests
python scripts/run_demo.py                  # terminal demo
shiny run app/app.py --port 8000            # console
python scripts/console_smoke.py --port 8000 # click-through over Shiny's websocket (needs the console running)
```

## Map

- `pitcrew/world.py` — the only place agents touch state. Every tool records `{agent, tool, args, result}` in
  `World.trace`. Add a capability = add a method here + a `@tool` wrapper in `crew/strands_crew.py`.
- `pitcrew/crew/` — `offline.py` (deterministic narration; the reference), `strands_crew.py` (Bedrock,
  GraphBuilder), `scripted_model.py` (fake Strands model for tests), `__init__.py` (`Crew` facade, fallback).
- `pitcrew/mill.py` — AI4I walls, Lift & Coast, Monte Carlo, mill economics.
- `pitcrew/tower.py` — `DriveModel` (all coefficients), `Fleet` simulation (48 towers, 3 sites, lots A/B/C,
  demo towers 7/19/31/42 scripted), detectors (`DETECTORS`: today's sensors vs future slots), `rul_days`,
  `project` (weather Monte Carlo under a tracking mode).
- `pitcrew/decide.py` — Park & Price; `TowerEconomics`; energy windows from the table.
- `pitcrew/kaizen.py`, `pitcrew/futures.py` — Improve loop.
- `pitcrew/passport.py` — manual tables → passport; slots; validate; sign.
- `pitcrew/solar_face.py` + `scripts/export_energy_table.py` — the Shadow Calculator field model with a free
  face azimuth; `--check-engine <path to janta-shadow-calculator/engine>` compares with `field_poa`.
- `app/app.py` — Shiny; one shared `Fleet` (deterministic, read-only), one `World` per session.
- `agentcore/agent.py` — AgentCore entrypoint (`action`: plan_mill, plan_tower, approve, improve, grow).

## Rules

- Never commit the FGA14 datasheet or any Janta-internal value not already public; the tower manual is
  public-safe on purpose. Only derived energy numbers come from the Shadow Calculator.
- Approval cards show tool numbers only. If a model-written number disagrees with a tool, the tool wins.
- Demo towers are scripted (`Fleet._inject_demo`); keep `tests/test_tower.py` green when retuning.

## Next steps, in value order

1. Fetch the real AI4I file in the workshop and rerun the tests (the replica's counts differ slightly).
2. Wire DuraMAT tracker motor current into `DriveModel` (baseline current per move and a real stall).
3. AgentCore Gateway + Policy for `World` tools; Bedrock Knowledge Base for `data/manuals/`.
4. A2A supplier runtime and an RFQ tool for the Quartermaster.
5. On Janta's server: rerun `export_energy_table.py` with the PVGIS typical year.
