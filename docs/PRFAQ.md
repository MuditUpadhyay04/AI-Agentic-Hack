# Working backwards: press release (draft)

**PitCrew: every task, every part, ready before it's needed**

*An agent crew that keeps semiconductor equipment running by knowing what will fail, what is down, and where
the part is.*

AUSTIN — PitCrew is a crew of AI agents for NXP's equipment fleet across fabs and assembly/test sites. It keeps
one priority queue of every maintenance task, predicts failures before they happen, puts emergencies at the
top, and makes sure the part is already at the nearest hub before the technician leaves.

Today, routine maintenance runs on calendars, failures are found when a tool stops, and the part is often a
day away. PitCrew changes the order of events. Lifelines schedule routine work weeks ahead. A failure model
scores every machine's live readings and moves a machine that is about to fail ahead of routine work. When a
tool does go down, that job jumps to the top, the part is pulled from the closest hub and the site is told
what to bring.

Underneath, the Sourcing agent keeps the hubs stocked: local hubs refill from the central hub, and the central
hub refills from verified vendors — the cheapest that still arrives in time, not the fastest at any price. The
Internal Fabrication agent watches the factory's own machines, so a degrading line is fixed in planned
downtime and in-house lead times stay honest.

"The technician used to find out what was wrong when they got there. Now the part is waiting at the hub,"
*(illustrative quote)*.

## FAQ

**Does the crew act on its own?** Within limits. Purchase orders up to $500 and internal emails go out
automatically; larger orders, external email and any change to how a machine runs wait for a person. Every
action is logged with the tool results behind it.

**How does it know a machine will fail?** A gradient-boosted model (XGBoost) trained on the AI4I 2020
predictive-maintenance dataset scores each reading — temperatures, spindle speed, torque and tool wear — and
the screen shows which reading is furthest from healthy peers.

**What runs on AWS?** Strands agents on Amazon Bedrock, deployed on Bedrock AgentCore Runtime, with tool calls
traced in CloudWatch.

**What is still a placeholder?** The fleet names, hubs, part numbers, prices and lifelines. The models and the
sensor readings are real.
