# Demo script — 3 minutes

Rehearse with the console (`shiny run app/app.py`) and `python scripts/run_demo.py`. The demo bar's buttons
1–3 drive the story; Reset starts over. Every number is a tool result; with Bedrock the words change, the
numbers do not.

| Time | Beat | Screen | Say |
|---|---|---|---|
| 0:00–0:20 | The problem | Priority queue | "NXP runs equipment across fabs and assembly/test sites. A down tool costs output every hour, and a part that isn't nearby turns hours into days. PitCrew keeps one queue for every task and makes sure the part is already close." |
| 0:20–0:45 | Maintenance | Priority queue | "Lifelines put routine jobs in the queue weeks ahead: a sensor module at 92% of rated life, a power board at 90%." |
| 0:45–1:20 | Prevention | Demo 1 → Prevention | "Matthew's XGBoost model scores every machine's live reading. Dicing saw 07 just jumped to 97% failure risk: torque 52 Nm with 218 minutes of tool wear, far from its healthy peers. Its job moves to the top of routine work, the site is emailed, the part is reserved." |
| 1:20–1:50 | Cure | Demo 2 → Cure | "Dicing saw 19 throws an overheat shutdown. Cure beats everything: cooling fan module pulled from Local hub North, technician rerouted, site lead and technician emailed with what to bring." |
| 1:50–2:25 | Sourcing | Parts & sourcing → Sourcing agent | "The Sourcing agent on Bedrock works the queue: local hub, then central, then buys. It picks Vendor C — the cheapest that still arrives in time — over the fastest, and the $492 PO auto-approves under policy." |
| 2:25–2:45 | Internal fab | Demo 3 → Internal fab | "Hari's model sees a Makino line degrading; in-house lead time slips, and Sourcing re-picks the cheapest option that still arrives in time." |
| 2:45–3:00 | Close | Architecture | "Strands agents on Amazon Bedrock, deployed on AgentCore Runtime, tools under policy. Every task, every part, ready before it's needed." |

## Questions to expect

- **"Is the data real?"** Each machine's reading is a real AI4I 2020 record scored by Matthew's trained model;
  the fleet names, hubs, prices and lifelines are placeholders.
- **"What if the agent is wrong?"** POs above $500 and every setpoint change need a person; every number on
  screen comes from a tool, and the trace shows which.
- **"Why not just rules?"** The math is rules on purpose. The agents choose, explain, coordinate parts and
  people, and draft the messages.
- **"Cost to run?"** Scoring and allocation use no LLM tokens; tokens are spent per incident, not per reading.
