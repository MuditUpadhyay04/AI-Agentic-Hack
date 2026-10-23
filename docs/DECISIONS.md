# Decisions made overnight (change any of them)

| # | Decision | Why | Change by |
|---|---|---|---|
| 1 | Lead the pitch with a tower owner's customer, prove on the provided mill data, then point the same crew at the towers | Judges score use of the provided data; a fielded product is the stronger story | DEMO_SCRIPT.md |
| 2 | Crew runs offline by default; Bedrock via `PITCREW_LLM=bedrock` | Demo never dies on a model or network error; numbers identical either way | env var |
| 3 | Numbers on the approval card come from tool results, never model text | "Assumptions easy to inspect"; no invented figures | `crew/strands_crew.py: plan()` |
| 4 | Shiny for Python console | Posit is a sponsor; Python end to end; one process | `app/app.py` |
| 5 | Tower "lift and coast" = Park & Price: track / coast (15° steps, stow at 30 mph) / park at best azimuth / technician tomorrow | Energy per tower-day is small (~$2.75), so failures and truck rolls dominate; the crew prices that honestly | `decide.py` |
| 6 | Next route = Thursday/Friday batched DFW route (Rosa M.) | Batching truck rolls is where O&M money is (Omnidian 2.37 vs 6.06 rolls/MW-yr) | `ops.py: Technician` |
| 7 | Policy: POs ≤ $500 auto-approve; every setpoint/park needs the foreman | The track's "without losing the human operator" | `ops.py: POLICY` |
| 8 | Tower drive model is simulated with labelled coefficients | No open slew-drive failure data exists; field data replaces it via Improve | `tower.py: DriveModel` |
| 9 | Tower manual is public-safe (class-typical values) | Vendor datasheets are proprietary | `data/manuals/tower_drive_manual.md` |
| 10 | Energy table: clear sky, 8 × 445 W (3.56 kWdc), other losses 0.90 | Placeholder module and losses; offline | `scripts/export_energy_table.py` |
| 11 | Demo towers 7, 19, 31, 42 are scripted to reach a set state today; history arises from the model | Repeatable demo; honest history for Kaizen and Sensor Futures | `tower.py: Fleet._inject_demo` |
| 12 | Sensor prices (grease sensor $85, AE $180, MEMS $25, torque $140) | Placeholders for R&D to replace | `futures.py: SLOTS` |

## Open questions for you

- Does the ST-1 controller log motor current per move and the encoder? (The crew assumes yes.)
- What can a ST-1 do in a hail storm — turn edge-on to the wind, or face away from the storm? (Needed
  before a hail-stow feature: industry guidance of ≥70° stow is for single-axis trackers.)
- The real truck-roll cadence and costs for DFW sites, and the drive's real lead time.
