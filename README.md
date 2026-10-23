# PitCrew — Run · Improve · Grow

An agent crew for the Austin Agentic AI Hackathon, Track 2 (Autonomic Shop Floor & Predictive Maintenance).
It watches machines, **buys time** when a failure wall is close, orders the part, books the technician — and
turns every repair into a better next machine. Proven on the organisers' data (AI4I 2020 mill), then
pointed at a fleet of solar towers.

| Loop | Cadence | What the crew does | Where to see it |
|---|---|---|---|
| **Run** | minutes | Sentinel → Diagnostician → Race Engineer → *Foreman approves* → Quartermaster → Dispatcher | `Run · Mill`, `Run · Towers` |
| **Improve** | weekly | Kaizen: rules found in data, supplier-lot rates, Sensor Futures, ST-2 design-change request | `Improve` |
| **Grow** | per machine / sensor / supplier | Onboarder: manual → asset passport with **future hardware slots** → human signs → agents start | `Grow` |

## Quick start (no AWS needed)

```bash
pip install -r requirements.txt          # Python 3.10+
python -m pytest -q                      # 24 tests, ~50 s
python scripts/run_demo.py               # the whole story in the terminal
shiny run app/app.py --port 8000         # the operator console -> http://localhost:8000
```

The crew runs **offline** by default: same tools, same numbers, narration written from the tool results.
In the workshop account switch it to Bedrock:

```bash
export PITCREW_LLM=bedrock
export PITCREW_MODEL_ID=<a model or inference profile the starter kit's infer.py confirmed>
shiny run app/app.py --port 8000
```

Any model error falls back to the offline crew for that step and says so on screen.

## The demo in three minutes

See [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md). Short version:

1. **Run · Mill.** Normal window → *Harder steel lot arrives* (torque 40 → 56 Nm, creeping 0.3 Nm/part) →
   *Crew: assess*. The Sentinel shows the power wall 2% away (~5 parts). The Race Engineer prices three
   options and recommends **Lift & Coast: 1,400 rpm, feed cut to 47 Nm** — nearest wall 36 parts away vs 30
   to shift change, 8% headroom kept — $4,141 expected vs $4,542 to stop now vs $24,742 to run as-is.
   Approve → setpoint written, insert reserved, PO auto-approved under policy, work order at shift change.
2. **Run · Towers.** 8 of 48 towers flagged. Tower 7 (supplier lot B grease): +33% energy per degree;
   66% chance of a stall in wind before Thursday's route. **Park & Price** recommends parking at 180° until
   the visit: $3 of energy instead of a ~$2,456 failure. Six more towers batched on the same truck roll.
3. **Improve.** Kaizen finds the AI4I overstrain wall from data (precision 1.00, recall 0.98), lot B failing
   6× as often as lot A, and two R&D findings: **15° step tracking gives up 0.16% of a year's energy while
   cutting drive starts 85%**, and today's sensors already flagged 35 of 38 past failures a week ahead —
   nobody was watching (~$572 per tower-year of value before any new hardware).
4. **Grow.** Onboard the lathe manual → passport → sign. Onboard the tower passport → install the
   acoustic-emission slot → Tower 42's bearing defect, invisible to today's sensors, lights up.

## How the numbers are made (and how to check them)

- **Mill walls** are AI4I 2020's published failure rules (UCI dataset 601): power 3.5–9 kW, tool wear ×
  torque under 11,000/12,000/13,000 min·Nm (L/M/H), heat dissipation below 1,380 rpm with a gap under
  8.6 K, tool wear 200–240 min. `pitcrew/mill.py`, checked in `tests/test_mill.py`.
- **AI4I data**: `python scripts/fetch_data.py` downloads the real file. Without internet PitCrew builds a
  seeded replica from the same published rules and labels every result with its source.
- **Tower energy** comes from a two-wing field model (`pitcrew/solar_face.py`: Perez sky, SAPM cell
  temperature, placeholder 0.90 other losses), exported by `scripts/export_energy_table.py`. Clear sky (an
  upper bound); rerun with a typical-year weather file for the real table. Late October: parking at 180° gives up ~20% of a day's energy.
- **Tower drive model** (`pitcrew/tower.py`) is a simulation with every coefficient in `DriveModel`:
  grease ageing (time, heat, churn per start, faster for lot B, steps after seal leaks), friction → energy
  per degree, wind load, stall when friction + gust exceed the motor, backlash growth (per start and per
  degree, faster on poor grease), IMS-shaped bearing defects. Signatures follow the field literature
  (rising drive current US11588425; reversal dead zone US10498193). Replace with field data as it arrives.
- **Prices** are assumptions on the approval card (`MillEconomics`, `TowerEconomics`): truck rolls from
  Power Factors ($125 local, $400 regional); the rest are placeholders.

## AWS

| Piece | Service | File |
|---|---|---|
| Agents | Strands Agents; `GraphBuilder` for Run (Sentinel → Diagnostician → Race Engineer; Quartermaster → Dispatcher after approval) | `pitcrew/crew/strands_crew.py` |
| Runtime | Bedrock AgentCore Runtime (`BedrockAgentCoreApp`) | `agentcore/agent.py` |
| Tools | The `World` tools; exposed through AgentCore Gateway as MCP in the workshop | `pitcrew/world.py` |
| Guardrails | Policy: POs over $500 and every setpoint change need the foreman (AgentCore Policy / Cedar; in code offline) | `pitcrew/ops.py` |
| Suppliers | A2A: a supplier agent on its own runtime (`serve_a2a`, port 9000) | `agentcore/supplier_a2a.py` |
| Knowledge | Manuals (Bedrock KB in AWS; keyword search offline), passports, incident history | `data/manuals/`, `pitcrew/passport.py` |

Setup steps for the morning: [docs/AWS_SETUP.md](docs/AWS_SETUP.md).

## Repository

```
pitcrew/          engine: mill.py, tower.py, decide.py (Park & Price), kaizen.py, futures.py (Sensor Futures),
                  passport.py, ops.py (parts, POs, roster, policy), solar_face.py, world.py (tools), viz.py
pitcrew/crew/     offline.py, strands_crew.py (Bedrock), scripted_model.py (tests), __init__.py (Crew facade)
app/              Shiny operator console
agentcore/        AgentCore entrypoint, A2A supplier agent
scripts/          fetch_data, export_energy_table, run_demo, console_smoke, invoke_agentcore
data/             energy table (derived numbers only), demo manuals
docs/             DEMO_SCRIPT, AWS_SETUP, DATASETS, DECISIONS, IDEAS, PRFAQ, architecture.svg
tests/            pytest suite
```

## Rules kept

- Nothing proprietary in this repo: no vendor datasheets; the tower manual is a public-safe summary with
  class-typical values; tower ratings and prices are placeholders.
- No number is typed by a model: every figure on an approval card comes from a tool result in the trace.
- Hackathon prototype, not a control system: setpoint "writes" change simulated state only.
