# Solar tower — slew drive operations summary (public-safe)

Public-safe summary for the hackathon account. It holds no values from the drive maker's proprietary
datasheet: ratings marked "class typical" are typical for a 14-inch worm slew drive. Fill exact ratings from
the maker's datasheet outside this repo.

- Asset class: Solar tower slew drive
- Model: ST-1 tower, 14-inch worm slew drive (class typical)
- Agent template: slew-drive-v1

## Operating limits

| Limit | Signal | Min | Max | Unit | Condition |
|---|---|---|---|---|---|
| Stall margin | energy per degree vs baseline, incl. wind |  | 1.5 | ratio | while moving |
| Backlash | reversal dead zone at the output |  | 0.5 | deg | replace the drive above |
| Grease | grease condition index | 0.10 |  | index | seizes below |
| Tracking wind | gust at the panel |  | 17.9 | m/s | stow above (40 mph) |
| Bearing | acoustic emission health index |  | 6 | index | replace the drive above |

## Signals

| Signal | Unit | Fitted today |
|---|---|---|
| Motor energy per move | Wh/deg | yes |
| Peak motor current | A | yes |
| Motor encoder (1024 pulses per motor turn) | counts | yes |
| Ambient temperature | C | yes |
| Site wind | m/s | yes |
| Grease condition (water, iron) | ppm | no |
| Worm-side vibration | g | no |
| Acoustic emission on the bearing | counts | no |
| In-drive torque | kN m | no |
| Output absolute encoder | deg | no |

## Maintenance

| Task | Interval |
|---|---|
| Re-grease the slew drive (more often after strong winds or extreme heat) | 24 months |
| Check seals for leaks and condensation | 6 months |
| Re-torque mounting bolts | 12 months |
| Nightly reversal test for backlash | daily |

## Parts

| Part number | Description |
|---|---|
| GREASE-KIT-SD | Slew-drive re-grease kit |
| SEAL-KIT-SD | Slew-drive seal kit |
| BOLT-KIT-SD | Drive mounting bolt kit |
| DRIVE-WSD14 | Worm slew drive, 14 in class |
