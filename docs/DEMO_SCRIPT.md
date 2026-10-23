# Demo script — 3 minutes, Run → Improve → Grow

Rehearse with `python scripts/run_demo.py` (terminal) and the console. Record a backup video of the console
after the 3:15 code freeze. Every number below is what the offline crew produces today; with Bedrock the
words change, the numbers do not.

| Time | Beat | Screen | Say |
|---|---|---|---|
| 0:00–0:20 | Customer first | Why (press release) headline | "People who host solar towers don't want a dashboard; they want the energy they were promised and no surprises. Your mill and a tower die the same way — so we built a crew that keeps both running." |
| 0:20–0:35 | Normal window | Run · Mill, before clicking | "AI4I's walls: power 3.5–9 kW, overstrain, heat, tool wear. Data window and labels are the published ones." |
| 0:35–1:20 | Sensor change → Lift & Coast | *Harder steel lot arrives* → *Crew: assess* → envelope | "Torque 56 Nm: 2% from the power wall, ~5 parts. The Race Engineer doesn't just predict — it buys time: 1,400 rpm, 47 Nm, still inside both walls at shift change. $4,141 vs $4,542 to stop now vs $24,742 to run on." Approve → work order + PO under policy. |
| 1:20–1:55 | Same crew, solar tower | Run · Towers → tower 7 → assess | "Lot-B grease, +33% energy per degree. 66% chance of a stall in wind before Thursday's route. Park & Price with our own energy model: park at 180° for $3 of energy instead of a $2,456 failure — and six more towers ride the same truck roll." Approve. |
| 1:55–2:25 | Improve | Improve → Run Kaizen | "The crew turns repairs into R&D: lot B fails 6× as often; 15° steps give up 0.16% of energy and cut drive starts 85% — that's how ST-2 will track. And today's sensors already saw 35 of 38 past failures a week ahead. Nobody was watching." |
| 2:25–2:45 | Grow (the Apple beat) | Grow → tower manual → install acoustic slot → Run · towers → 42 | "We design for hardware we haven't shipped. Each passport has empty slots; the agents already exist. Install acoustic emission and tower 42's bearing — invisible until now — lights up with 19 days left. The crew also prices which sensor is worth adding next." |
| 2:45–3:00 | Close | Architecture | "Strands on AgentCore, tools under Policy, suppliers over A2A. Priced per tower, so the crew grows with every machine it onboards." |

## Questions to expect

- **"AI4I is synthetic."** That is why its walls are exact; on a real machine the passport's walls come
  from the manual and get tightened by the Kaizen loop.
- **"Your tower data is simulated."** Yes, and labelled. The energy numbers are from a two-wing field
  model with placeholder ratings; the drive model's signatures come from field literature and
  will be replaced by the fleet's own data — that is the Improve loop.
- **"What if the agent is wrong?"** Setpoint changes and POs above $500 always need the foreman, and every
  option shows its risk, margin and assumptions.
- **"Why not just rules?"** The walls are rules on purpose. Agents choose between priced options, read
  manuals, coordinate parts and people, and write new rules from history.
- **"Cost to run?"** The Sentinel uses no model; tokens are spent per incident, not per sensor tick.
