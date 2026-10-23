# Prompt: build the PitCrew pitch simulation

Copy everything below the line into Claude.

---

You are building the animated simulation our team will show on a projector while we pitch at the Austin
Agentic AI Hackathon (Track 2: Autonomic Shop Floor & Predictive Maintenance). The challenge customer is
NXP Semiconductors. Our product is called **PitCrew**.

The judges will watch this while we talk. **The most important requirement is low cognitive load:** a
calm, simple, clean animation where only one thing moves at a time and every movement has an obvious
meaning. If you are unsure whether to add something, leave it out.

## 1. The story the simulation must tell

PitCrew keeps every part our company has deployed at customer sites working, using **one priority queue**
of tasks that is fed by three sources, all supported by our manufacturing and supply chain.

1. **Maintenance (routine).** A lifeline model knows the part number of every part deployed at every
   customer site, along with its datasheet and rated life. It schedules routine tasks into the queue ahead
   of time: "this part needs maintenance", "that part needs replacement".
2. **Prevention (predicted failure).** A failure-prediction model watches the products and every now and
   then says "a failure is going to happen in this product / this part". That task **outranks routine
   maintenance** and moves up the queue.
3. **Cure (something is down).** Something went down at a customer site — a natural disaster, a power
   surge, force majeure. The customer needs the part or product back up as soon as possible. That task
   goes **straight to the top** of the queue, and the nearest local hub is mobilised.
4. **Supply chain (supports all three).** Underneath, our manufacturing and supply chain support all
   three at the same time:
   - When a task uses a part, the **local hub's** stock goes down.
   - If the local hub doesn't have the part, or runs low, the **central hub** sends stock to it.
   - When the central hub runs low, the **Sourcing agent** goes through the **verified vendor list**, finds
     the right option (cheapest that still arrives in time vs fastest) and replenishes the central hub.
   - The **Internal Fabrication agent** watches our own factory machinery so any internal issue is fixed
     without hampering manufacturing.

## 2. What to build

- **One self-contained HTML file** (inline CSS and JS; no build step). It must run offline from a laptop
  (`file://`), with no network calls. Use the system font stack (no web fonts). Vanilla JS + inline SVG is
  preferred; if you use React, load it from a pinned CDN version and make sure it still works if the CDN is
  cached — but vanilla is safer for a live demo.
- **Fixed 16:9 stage, designed at 1920×1080**, scaled to fit the window with letterboxing (keep the aspect
  ratio; never scroll; never reflow). It will be shown on a projector, so it must read from the back of a
  room.
- **Light theme** (projectors wash out dark themes).
- **Deterministic and scripted.** No randomness. Every number comes from the `SCENARIO` data in section 7,
  so running it twice gives exactly the same show.
- **Presenter-paced.** It advances one step at a time when the presenter presses a key, so the animation
  never runs ahead of the talk. An autoplay mode exists for rehearsal and for recording a backup video.

## 3. Screen 1 — the main view

Three horizontal bands, top to bottom:

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│ PitCrew                                                   Fri Oct 23 · 10:00   ● ● ○ ○ ○  │
├──────────────────────────────────────────────────────────────────────────────────────────┤
│ PRIORITY QUEUE   [Queue agent: "Cure outranks everything: a customer is down."]          │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐                                    │
│  │ #1   │ │ #2   │ │ #3   │ │ #4   │ │ #5   │ │ #6   │   +1 more                          │
│  └──────┘ └──────┘ └──────┘ └──────┘ └──────┘ └──────┘                                    │
│        ▲                    ▲                     ▲      (cards fly up from the columns)   │
├──────────────────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────┐   ┌─────────────────────┐   ┌─────────────────────┐              │
│  │ MAINTENANCE         │   │ PREVENTION          │   │ CURE                │              │
│  │ routine, from rated │   │ predicted failure   │   │ something is down   │              │
│  │ life                │   │                     │   │                     │              │
│  │ (source + new task) │   │ (source + new task) │   │ (source + new task) │              │
│  └─────────────────────┘   └─────────────────────┘   └─────────────────────┘              │
│            ▲                          ▲                          ▲                        │
├──────────────────────────────────────────────────────────────────────────────────────────┤
│ ████████  MANUFACTURING & SUPPLY CHAIN  — supports all three  (click to open)  ████████   │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

**Top band — Priority queue (about 30% of the height).**
- A single row of task cards, **left = highest priority (#1)**. Show at most 6 cards; the rest collapse into
  a quiet "+N more" pill.
- A small **Queue agent** chip at the start of the row, with a speech-bubble caption of **at most 10 words**
  explaining its latest decision (texts in section 7). The caption changes only when the queue changes.
- **Task card** (about 250×150 px): a coloured top edge in the task type's colour, a type label
  (MAINTENANCE / PREVENTION / CURE), the task ID, the **part number in large type** (this is the
  link to the supply chain), the part name, the customer site, and one short reason line. Nothing else.
- Re-ordering is animated with a smooth slide (FLIP technique): when a card is inserted ahead of others,
  the others slide right to make room. Never teleport a card.

**Middle band — the three sources (about 45%).**
- Three equal columns, left to right: **Maintenance, Prevention, Cure** (urgency rises left to right).
- Each column shows: an icon, the title, a one-line subtitle, and the model or agent that feeds it:
  - Maintenance: "Lifeline model — rated life from each part's datasheet"
  - Prevention: "Failure-prediction model"
  - Cure: "Incident response — disasters, outages, force majeure"
- When a column produces a task, the new card appears inside its column first (so the eye sees where it
  came from), holds for about 0.6 s, then **flies up** into its slot in the queue.
- Between events the columns are quiet. No live charts, no ticking numbers.

**Bottom band — Manufacturing & supply chain (about 15%).**
- A full-width bar in the supply-chain colour, labelled **"Manufacturing & Supply Chain"** with a small
  subtitle "supports all three". Three arrows rise from it, one into each column.
- Idle state: the three arrows have a slow, subtle upward pulse (about one pulse every 3 s, low opacity).
- When a task needs a part, the arrow under that task's column pulses once, brighter.
- The bar is **clickable** (and has a keyboard shortcut) and opens the Supply chain dialog. It shows a
  small "Open ↗" affordance at the right so the audience knows it opens.

## 4. Screen 2 — the Supply chain dialog

A modal that covers about 88% of the stage, over a dimmed main view. It opens with a quick scale/fade
(250 ms). Layout:

```
┌───────────────────────────────────────────────────────────────────────────────────────┐
│ Manufacturing & Supply Chain                                                    ✕     │
├──────────────┬────────────────────────────────────────────────────────────────────────┤
│ PRIORITY     │ [Internal Fabrication agent]                    [Sourcing agent]       │
│ QUEUE        │                                                                        │
│ (compact,    │     site ○      ○ site                     ○ site     ○ site           │
│  vertical,   │          \    /                                 \    /                 │
│  same order  │        [ Local hub North ]               [ Local hub East ]           │
│  as main)    │                    \                         /                         │
│ ▸ CUR-007    │  [Factory]──[        CENTRAL HUB        ]          ║ Verified vendors ║ │
│ ▸ PRV-031    │                    /                         \     ║ Vendor A         ║ │
│ ▸ MNT-198    │        [ Local hub West ]                [ Local hub South ]  Vendor B │
│ ▸ ...        │          /    \                                 /    \        Vendor C │
│              │     site ○      ○ site                     ○ site     ○ site           │
├──────────────┴────────────────────────────────────────────────────────────────────────┤
│ Caption: one plain sentence about what is happening now                               │
└───────────────────────────────────────────────────────────────────────────────────────┘
```

- **Left column (about 22% wide): the priority queue**, compact and vertical, in the same order as on the
  main view. The task currently being served is highlighted. When its part is on site, it shows a small
  check and the text "part on site".
- **Network map (the rest), drawn in SVG:**
  - **Central hub** in the middle — the largest node, a warehouse icon.
  - **Four local hubs** around it (North, East, South, West), each connected to the central hub by a
    line.
  - **Two customer sites** per local hub on the outer ring — small circles connected to their local hub.
  - **Factory** (internal fabrication) attached to the left side of the central hub, with a thin line into
    it (the factory supplies the central hub).
  - **Verified vendors** on the right edge, as a small stacked list of 3 vendor nodes plus 1 greyed,
    unverified vendor (it exists to show that the agent only uses verified vendors).
- **The two agents sit in the two top corners of the map:** the Internal Fabrication agent top-left (near
  the factory) and the Sourcing agent top-right (near the vendors). Each is a small card with an icon,
  its name, and a status line of **at most 10 words** that changes when it acts. When an agent acts, its
  card gets a soft glow and a thin dotted "attention" line to the node it is acting on.
- **Stock badges:** next to each hub, show the stock of **only the part number that is in play right now**,
  as `PN-2210 · 2`. Hide all other numbers. A badge turns amber when it is at or below its reorder level and
  green when it is restocked; when a number changes it counts down/up over about 400 ms.
- **Movement:** a shipment is a small solid dot (with a tiny part-number tag) that travels along the line
  between two nodes in 1.2–1.8 s with ease-in-out. Shipments for a Cure task are red and slightly faster.
  Only **one** shipment moves at a time.
- **Bottom caption bar:** one plain sentence describing the current step (texts in section 7).

## 5. The script (steps)

The presenter presses → (or Space) to go to the next step. Each step runs its animations in sequence and
then waits. The simulated clock in the header advances as listed. Card IDs, part numbers and stock
numbers must match section 7 exactly.

**Main view**

| Step | Clock | What happens | Queue agent caption |
|---|---|---|---|
| 0 | Fri Oct 23 · 10:00 | Opening state: the queue holds MNT-198, MNT-199 and MNT-200 (due-date order). Columns quiet. Supply-chain arrows pulsing softly. | "Routine work, ordered by due date." |
| 1 | 10:05 | **Maintenance.** The Lifeline model produces MNT-201, which flies up into slot #4 (after MNT-200, by due date). Then MNT-202 flies into slot #5. | "New lifeline tasks, added by due date." |
| 2 | 11:40 | **Prevention.** The Failure-prediction model flags PRV-031 (PN-1043 cooling fan module at Site E1, failure predicted in 5 days, 80%). The card appears in the Prevention column, flies up and **takes slot #1**; the five maintenance cards slide right one place. | "Predicted failure outranks routine maintenance." |
| 3 | 13:15 | **Cure.** A storm causes a power surge at Site S2 and the line is down. CUR-007 (PN-2210 power supply board) appears in the Cure column with a single red pulse, flies up and **takes slot #1**; everything else slides right; the queue now shows 6 cards + "+1 more". A small tag under CUR-007 reads "Mobilising Local hub South". | "Cure outranks everything: a customer is down." |
| 4 | 13:16 | **Supply chain.** The three arrows from the supply-chain bar pulse brighter one after another (Maintenance → Prevention → Cure), then the bar highlights to invite a click. The dialog opens on the next step (or when the bar is clicked). | (unchanged) |

**Supply chain dialog**

| Step | Clock | What happens | Agent status | Caption |
|---|---|---|---|---|
| 5 | 13:16 | Dialog opens. CUR-007 is highlighted in the queue. Local hub South's badge shows `PN-2210 · 2`. A red shipment dot goes Local hub South → Site S2. The badge counts 2 → 1 and turns amber (reorder level 2). CUR-007 gets "part on site". | Sourcing: "Watching stock for PN-2210." | "Cure first: Local hub South sends the power supply board to Site S2." |
| 6 | 13:30 | PRV-031 is highlighted. Local hub East's badge shows `PN-1043 · 0` and briefly flashes "not in stock". Central hub's badge shows `PN-1043 · 15`. A shipment of 3 goes Central → Local hub East: central 15 → 12 (stays green, reorder level 10), East 0 → 3. Then one dot goes East → Site E1: East 3 → 2. PRV-031 gets "part on site". | Sourcing: "Local hub East had none: central sent 3." | "Local hub East didn't have the fan module, so the central hub sent it — plus 2 spares for future jobs." |
| 7 | 13:45 | The Sourcing agent glows and its attention line points to Local hub South (`PN-2210 · 1`, amber). A shipment of 3 goes Central → Local hub South: South 1 → 4 (green); central `PN-2210` 11 → 8, which turns amber (reorder level 10). | Sourcing: "Restocked South. Central is low on PN-2210." | "The central hub restocks the local hub so it's ready for the next job." |
| 8 | 13:50 | **Vendor choice.** A small card slides out from the Sourcing agent over the vendor list (section 7, Vendor table): order 12 × PN-2210, need by **Mon Nov 2**. Vendor D is greyed out and labelled "not verified". Vendor A is labelled "cheapest, but arrives Nov 5 — too late". Vendor B is labelled "fastest: Oct 27, $552". Vendor C is highlighted as the choice: "cheapest in time: Oct 30, $492". Below it: "PO-7711 auto-approved (under $500 policy)". | Sourcing: "Vendor C: cheapest that arrives in time." | "The Sourcing agent checks only verified vendors and picks the cheapest one that still arrives in time." |
| 9 | Fri Oct 30 | The clock jumps forward (show the date change clearly, e.g. a soft flip). A shipment of 12 goes Vendor C → Central hub: central `PN-2210` 8 → 20 (green). | Sourcing: "Central hub restocked: 20 PN-2210." | "A week later the order arrives, and the central hub is back to full stock." |
| 10 | Fri Oct 30 · 16:00 | **Internal fabrication.** The Internal Fabrication agent glows; its attention line points to the Factory. The factory node shows a small amber dot: "Test station T-4: vibration rising, ~30 h to failure". Then: "Fix booked in tonight's planned downtime, 02:00–04:00". The amber dot turns green; a small "Output on plan" tag appears on the factory → central hub line. | Internal Fab: "T-4 fixed in planned downtime. Output on plan." | "Inside our own factory, the Internal Fabrication agent fixes machine issues before they stop production." |
| 11 | — | Dialog closes (reverse of the open). | — | — |

**Back on the main view**

| Step | Clock | What happens | Queue agent caption |
|---|---|---|---|
| 12 | — | CUR-007 completes: the card turns green, shows "Back up in 4 h" with a check, then lifts out of the queue; the others slide left. Then PRV-031 completes: "Replaced before it failed", lifts out. | "Customer back up. Failure prevented." |
| 13 | — | Closing frame: the queue shows the remaining routine tasks, all three columns are calm, the supply-chain arrows pulse together once, and a centred tagline fades in: **"Every task, every part — ready before it's needed."** (placeholder tagline, easy to edit). | — |

The **← key** steps back. It must produce exactly the state of the previous step, with no half-finished
animations. The simplest way is to rebuild state by replaying steps 0..n-1 without animation, then
render.

## 6. Visual design

- **Colours** (CSS variables at the top of the file so the team can retheme):
  - background `#F8FAFC`, surface `#FFFFFF`, text `#0F172A`, muted text `#64748B`, lines `#CBD5E1`
  - Maintenance blue `#2563EB`, Prevention amber `#D97706`, Cure red `#DC2626`
  - Supply chain teal `#0F766E`; stock OK green `#16A34A`; stock low amber `#D97706`
- Colour always means the same thing everywhere: blue = maintenance, amber = prevention *and* "low", red
  = cure/urgent, teal = supply chain, green = OK. Don't introduce other accent colours.
- **Type** at 1920×1080: titles 40 px, column headings 28 px, card part number 30 px bold, body and
  captions at least 22 px, smallest label 18 px. System font stack; tabular numbers for stock counts.
- **Icons:** simple inline-SVG line icons (wrench = maintenance, pulse/chart = prevention, alert triangle =
  cure, warehouse = hub, factory, truck/dot = shipment, small robot or spark = agent). No emoji, no
  images, no logos (no NXP or any other company logo).
- **Motion:** ease-in-out, 300–800 ms for UI changes, 1.2–1.8 s for shipments. One thing moves at a time;
  sequence the steps instead of overlapping them. Respect `prefers-reduced-motion` (fade instead of fly).
- **Calm:** generous whitespace, lots of empty space around the network map, thin lines (1.5–2 px),
  rounded corners (12 px), soft shadows. No gradients except the subtle arrow pulse. No more than about 7
  numbers on screen at once.
- The header shows "PitCrew" (left) and the simulated clock plus small step-progress dots (right).

## 7. Scenario data (use exactly these values; put them in one `SCENARIO` object at the top of the script)

All names and numbers are placeholders the team will edit later. Keep them in data, not scattered through
the code.

**Parts**

| Part number | Name |
|---|---|
| PN-1043 | Cooling fan module |
| PN-2210 | Power supply board |
| PN-3307 | Sensor module |
| PN-4518 | Controller board |

**Network**

- Central hub (centre), with Factory attached.
- Local hubs: North, East, South, West.
- Customer sites: N1, N2 (North); E1, E2 (East); S1, S2 (South); W1, W2 (West).
- Verified vendors: Vendor A, Vendor B, Vendor C. Unverified: Vendor D.

**Starting stock (only these appear on screen)**

| Location | Part | Start | Reorder level | Target |
|---|---|---|---|---|
| Local hub South | PN-2210 | 2 | 2 | 4 |
| Local hub East | PN-1043 | 0 | 1 | 3 |
| Central hub | PN-1043 | 15 | 10 | 20 |
| Central hub | PN-2210 | 11 | 10 | 20 |

Check: South 2 → 1 (Cure) → 4 (+3 from central). East 0 → 3 (+3 from central) → 2 (Prevention). Central
PN-1043 15 → 12. Central PN-2210 11 → 8 (sent 3 to South) → 20 (+12 from Vendor C).

**Tasks**

| ID | Type | Part | Site | Reason line | Due / timing |
|---|---|---|---|---|---|
| MNT-198 | Maintenance | PN-3307 Sensor module | E2 | Rated 20,000 h · now at 18,900 h | Due Nov 6 |
| MNT-199 | Maintenance | PN-1043 Cooling fan module | S1 | Rated 3 years · installed Nov 2023 | Due Nov 9 |
| MNT-200 | Maintenance | PN-2210 Power supply board | N1 | Rated 50,000 h · now at 47,800 h | Due Nov 12 |
| MNT-201 | Maintenance | PN-3307 Sensor module | W1 | Rated 20,000 h · now at 18,600 h | Due Nov 14 |
| MNT-202 | Maintenance | PN-4518 Controller board | N2 | Rated 5 years · installed Nov 2021 | Due Nov 20 |
| PRV-031 | Prevention | PN-1043 Cooling fan module | E1 | Failure predicted in 5 days (80%) | Predicted Oct 28 |
| CUR-007 | Cure | PN-2210 Power supply board | S2 | Storm power surge · line down | Now |

**Vendors for 12 × PN-2210, need by Mon Nov 2 (ordered Fri Oct 23)**

| Vendor | Verified | Unit price | Lead time | Arrives | Total | Label |
|---|---|---|---|---|---|---|
| Vendor A | Yes | $38 | 13 days | Nov 5 | $456 | cheapest, but too late |
| Vendor B | Yes | $46 | 4 days | Oct 27 | $552 | fastest |
| Vendor C | Yes | $41 | 7 days | Oct 30 | $492 | **choice: cheapest in time** |
| Vendor D | No | $31 | 5 days | — | — | not verified, excluded |

Policy: purchase orders up to $500 are auto-approved; above that a planner approves.

**Factory event:** Test station T-4, vibration rising, about 30 h to failure; fix booked in the planned
downtime 02:00–04:00; output stays on plan.

## 8. Controls

| Key | Action |
|---|---|
| → or Space | Next step |
| ← | Previous step |
| R | Reset to step 0 |
| S | Open/close the Supply chain dialog by hand (clicking the bar does the same) |
| A | Toggle autoplay (each step holds about 10 s; the full show runs in about 2.5 minutes) |
| C | Show/hide the caption bar |
| N | Show/hide speaker notes (a small panel with the step's caption and what to say) |
| F | Fullscreen |

Show a tiny, low-contrast hint "→ next · ← back" in the bottom-right corner that fades out after the first
key press. No other on-screen controls during the show.

## 9. How to structure the code

- `SCENARIO` (data) → `STEPS` (an array; each step is `{ clock, apply(state), animate(state, prev) }`) →
  `render(state)` (pure: draws everything from state) → a small timeline runner that runs `animate` and
  then commits `render`.
- Queue order is computed, not hand-placed: Cure first, then Prevention, then Maintenance; within a type,
  by due date. That way, adding a task in the data reorders the queue correctly.
- Shipments animate along the actual SVG line between the two nodes (`getPointAtLength`), so the layout can
  change without breaking the animation.
- Keep it in one file under about 1,500 lines. Comment the `SCENARIO` and `STEPS` sections so a teammate
  can change names, numbers and captions without reading the rest.

## 10. Do not

- Add charts, tables full of numbers, dashboards, maps of real geography, or extra panels.
- Animate two things at once, or anything continuously except the soft arrow pulse.
- Invent numbers or names that are not in section 7.
- Use real company names, logos or people's names in the UI.
- Use dark mode, tiny text, or anything that needs scrolling.
- Depend on the internet at show time.

## 11. Done when

- [ ] Opening the file offline shows step 0 at full 16:9, letterboxed in any window size.
- [ ] → walks through steps 0–13 exactly as in section 5; ← goes back to an identical previous state.
- [ ] Clicking the supply-chain bar or pressing S opens the dialog at any point.
- [ ] Every stock number on screen matches section 7, and the arithmetic adds up.
- [ ] At every step, at most one thing is moving and the caption explains it in one sentence.
- [ ] All text is at least 18 px at 1920×1080 and readable from 5 m on a projector.
- [ ] Autoplay runs the whole story in about 2.5 minutes without input.
- [ ] No console errors; no network requests.

When you're done, tell me in a short list which values to change in `SCENARIO` and `STEPS` for a different
story, and anything you had to assume.
