# Idea index — what is built, what is stretch, where to look

| Idea | One line | Status | See it |
|---|---|---|---|
| Lift & Coast (mill) | Derate inside the safe envelope to reach the cheapest maintenance window | **Built** | Run · Mill → envelope chart |
| Park & Price (tower) | Price track / coast / park / technician-tomorrow with the energy model and a weather Monte Carlo | **Built** | Run · Towers |
| Truck-roll batching | Dispatcher rides other flagged towers on the same route | **Built** | tower approval card |
| Policy gate | POs over $500 and every setpoint change wait for the foreman | **Built** (code); AgentCore Policy in AWS | approval cards, `ops.py` |
| Kaizen rule discovery | Finds AI4I's walls from data with precision/recall | **Built** | Improve |
| Supplier-lot analysis | Failure rate per tower-year by lot with 90% intervals; re-grease interval per lot | **Built** | Improve |
| Step-tracking R&D finding | 15° steps: −0.16% energy, −85% drive starts (DCR-1) | **Built** | Improve tiles, DCR |
| Sensor Futures | Replay failures with each future sensor; value per tower-year and payback | **Built** | Improve |
| ST-2 design-change request | Kaizen drafts DCRs with evidence and a test plan | **Built** | Improve |
| Asset passport + onboarding | Manual → walls, signals, slots, parts → human signs → agents start | **Built** | Grow |
| Future hardware slots | Install a slot → detectors switch on fleet-wide (tower 42 appears) | **Built** | Grow → Run · towers |
| Supplier choice by lead time and field MTBF | Not the cheapest: the one that arrives in time and lasts | **Built** (catalogue); A2A agent ready | Quartermaster turn, `ops.py` |
| A2A supplier negotiation | Quartermaster talks to a supplier's own agent | Stretch: `agentcore/supplier_a2a.py` | — |
| Hail-stow proof pack | Forecast-triggered stow + insurer-ready logs (hail = 73% of PV weather losses) | Not built — needs the ST-1 stow geometry | — |
| Warranty evidence agent | Assemble telemetry proving the drive ran within ratings | Not built (Improve-loop follow-up) | — |
| Availability-guarantee pricer | Monte Carlo over fleet RUL to price an uptime contract | Not built (future business line) | — |
| Vibration Detective (CWRU) | Envelope spectrum vs bearing fault frequencies | Not built | — |
| Care Huddle (Track 1) | Five personas, disagreement made visible, for family caregivers | Not built — see the playbook | — |
