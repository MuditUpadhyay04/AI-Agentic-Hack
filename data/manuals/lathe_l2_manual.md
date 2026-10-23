# L-2 CNC turning centre — maintenance manual (demo manual)

Demo document for the Grow step: a machine the crew has never seen. Dropping this file onto the floor map
makes the Onboarder write its passport and spin up its agents.

- Asset class: CNC lathe
- Model: L-2
- Agent template: rotating-machine-v1

## Operating limits

| Limit | Signal | Min | Max | Unit | Condition |
|---|---|---|---|---|---|
| Spindle power | torque x angular speed | 1500 | 15000 | W | always |
| Spindle bearing temperature | bearing temperature |  | 70 | C | always |
| Hydraulic pressure | chuck hydraulic pressure | 18 | 35 | bar | while clamped |
| Coolant pressure | coolant pressure | 4 |  | bar | while cutting |
| Spindle vibration | velocity RMS |  | 4.5 | mm/s | alarm level (demo value) |

## Signals

| Signal | Unit | Fitted today |
|---|---|---|
| Spindle speed | rpm | yes |
| Spindle torque | Nm | yes |
| Spindle bearing temperature | C | yes |
| Hydraulic pressure | bar | yes |
| Coolant pressure | bar | yes |
| Spindle vibration | mm/s | no |
| Way-oil level | % | no |

## Maintenance

| Task | Interval |
|---|---|
| Way-oil top-up | weekly |
| Chuck jaw grease | 40 h |
| Hydraulic oil change | 4000 h |

## Parts

| Part number | Description |
|---|---|
| CHUCK-SEAL-L2 | Chuck cylinder seal kit |
| HYD-FILTER-L2 | Hydraulic filter |
