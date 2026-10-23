# VM-07 vertical machining centre — operations and maintenance (demo manual)

Demo document written for PitCrew. Limits follow the AI4I 2020 dataset's published failure rules so every
number the crew uses can be checked against the dataset.

- Asset class: CNC vertical mill
- Model: VM-07
- Agent template: rotating-machine-v1

## Operating limits

| Limit | Signal | Min | Max | Unit | Condition |
|---|---|---|---|---|---|
| Spindle power | torque x angular speed | 3500 | 9000 | W | always |
| Overstrain, L-grade stock | tool wear x torque |  | 11000 | min*Nm | product L |
| Overstrain, M-grade stock | tool wear x torque |  | 12000 | min*Nm | product M |
| Overstrain, H-grade stock | tool wear x torque |  | 13000 | min*Nm | product H |
| Heat dissipation | process minus air temperature | 8.6 |  | K | when speed < 1380 rpm |
| Tool life | tool wear | | 200 | min | replace between 200 and 240 min |

## Signals

| Signal | Unit | Fitted today |
|---|---|---|
| Spindle speed | rpm | yes |
| Spindle torque | Nm | yes |
| Air temperature | K | yes |
| Process temperature | K | yes |
| Tool wear counter | min | yes |
| Spindle vibration | g | no |
| Coolant condition | ppm | no |

## Maintenance

| Task | Interval |
|---|---|
| Replace insert at shift change when tool wear > 180 min | per shift |
| Spindle bearing grease check | 2000 h |
| Coolant concentration check | weekly |

## Parts

| Part number | Description |
|---|---|
| INSERT-CNMG-L | Carbide insert, L-grade steel |

## Tool change procedure (p. 42)

Stop the spindle, retract to tool-change height, lock out, replace the insert, touch off, run one test part
and measure before releasing the cell. A planned change at shift change takes about 15 minutes.
