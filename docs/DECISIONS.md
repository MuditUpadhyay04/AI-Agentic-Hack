# Decisions (change any of them)

| # | Decision | Why | Change by |
|---|---|---|---|
| 1 | Build for NXP Semiconductors: equipment at fab and assembly/test sites, a central hub at the factory and local hubs near the sites | The challenge customer; "Internal fab" maps directly onto a wafer fab | `pitcrew/contracts.py: Plant`, `HUBS` |
| 2 | One priority queue: Cure > Prevention > Maintenance, then due date; stock is allocated in queue order so a part is never promised twice | One list for technicians and one source of truth for Sourcing | `contracts.py: Plant.queue`, `sourcing.py: rank` |
| 3 | Prevention = Matthew's XGBoost model on the AI4I features; ≥ 70% risk pulls the job forward, 40–70% adds predicted demand | A trained model on real data; thresholds match Hari's model so the two read the same way | `contracts.py: ACT, WATCH` |
| 4 | Each machine's reading is a real AI4I record; the demo's "drift" is record 162 (overstrain: 52.3 Nm, 218 min tool wear) | Real data scored by the real model, no invented sensor values | `Plant.products[*].udi`, `Plant.DRIFT_UDI` |
| 5 | Sourcing ladder: local hub → central hub → another local hub → buy; buy the cheapest verified vendor that arrives by the need-by date, show the fastest beside it | Speed only where the date needs it; unverified vendors never chosen | `pitcrew/sourcing.py` |
| 6 | Policy: POs ≤ $500 auto-approve; every setpoint change needs the foreman; external email needs a manager | Keeps the human operator in the loop (Track 2) | `ops.py: POLICY`, `ALERT_POLICY` |
| 7 | Crew runs offline by default; Bedrock via `PITCREW_LLM=bedrock` (Sonnet 4.5 is on the workshop allowlist) | The demo never dies on a model or network error; numbers identical either way | env vars |
| 8 | Numbers on screen come from tool results, never model text | No invented figures; every tool call is in the trace | `crew/strands_crew.py`, `World.trace` |
| 9 | Shiny for Python console | Python end to end; one process | `app/app.py` |
| 10 | Fleet, hubs, part numbers, vendors, prices and lifelines are placeholders | No customer data in the repo | `contracts.py`, `sourcing.py` |

## Open questions

- Which NXP equipment and sites should the demo fleet name, and which parts matter most?
- Real lifelines (rated life per component) for the Maintenance pipeline.
- Error codes that mean "down" (Cure) vs "warning" for the target equipment.
- Real hub locations, transit times and the authorized vendor list.
