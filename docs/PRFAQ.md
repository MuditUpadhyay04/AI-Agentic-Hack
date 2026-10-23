# Working backwards: press release (draft, dated two years out)

**Janta Power launches PitCrew: solar towers that look after themselves**

*Commercial hosts in Texas get towers that see their own wear, protect themselves until the technician
arrives, and get better with every repair.*

DALLAS, October 2028 — Janta Power today made PitCrew standard on every Janta tower. PitCrew is a crew of
AI agents that watches each tower's slew drive, prices what to do when one starts to wear, orders the part,
books the technician, and turns every repair into a better next tower.

Facility managers who host solar on a warehouse roof or a data center lot don't want another dashboard.
They want the energy they were promised, and no surprises. Today a stuck tracker is found when a monthly
report looks low; a technician drives out to diagnose it, then drives back with the part. Meanwhile the
tower sits pointed at the wrong part of the sky.

With PitCrew, the tower notices first. When a drive's friction rises, the crew checks the next windy day
in the forecast, and if the drive might stall before the technician's route reaches it, it proposes to park
the tower at its best fixed angle — a few dollars of energy instead of a two-thousand-dollar failure. The
site's foreman taps Approve. The grease kit is already reserved, the visit is already on Thursday's route,
and five other towers due for service ride on the same truck roll.

"I found out about the problem from the work order, not from the outage," said the facility manager of a
DFW data center hosting 300 towers *(illustrative customer quote)*.

"Every repair now makes the next tower better," said the Janta Power founder *(placeholder)*. "The crew
showed us that stepping our towers in 15-degree moves gives up a sixth of a percent of energy and cuts
drive starts by 85 percent — so that's how TR-09 tracks. And it told us which sensor to add before we
built it."

PitCrew is included with every Janta service plan. Towers already in the field get it with a software
update; sensors added to new towers switch on new agents automatically.

## FAQ — customers

**Does the crew control my towers?** Within limits you set. Safety stow is automatic; anything that changes
output — parking a tower, a new setpoint — or spends money above the policy limit waits for a person to
approve it, and every action is logged with its evidence.

**What does it cost?** It is part of the service plan, priced per tower per month, set below the cost of one
truck roll a year. *(Hypothesis to test with the first five customers.)*

**What happens to my data?** It stays in Janta's AWS account and is used to run and improve your towers.

**What if the crew is wrong?** Every recommendation shows the risk it is managing, the margin it keeps and
the assumptions behind the prices. If a part fails anyway, the evidence packet supports the warranty claim.

## FAQ — internal

**Who is the customer?** The host's facility manager (uptime, no surprises), the host's insurer (proof of
stow during hail), and Janta's own technicians (fewer, better-planned truck rolls).

**Why now?** Agents on Bedrock AgentCore can call real tools under policy, AWS retired its own managed
predictive-maintenance service (Lookout for Equipment, Oct 7, 2026), and the tower fleet is young enough to
build the failure record right from the start.

**What must be true?** Every work order closes with a verified failure mode (a lightweight FRACAS); passports
are signed by engineering; the energy model stays calibrated against installed towers.

**What is the biggest risk?** Promising an availability guarantee before the failure data can price it.
PitCrew earns the right to guarantee by first proving it catches failures early.
