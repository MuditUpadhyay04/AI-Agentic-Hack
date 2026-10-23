# Datasets

| Dataset | Used for | Access | Status in repo |
|---|---|---|---|
| AI4I 2020 (UCI 601), 10,000 rows, CC BY 4.0 | Mill walls, Kaizen rule search | `scripts/fetch_data.py` | Seeded replica from the published rules until the real file is fetched; every output names its source |
| ST-1 tower energy table | Park & Price energy, step-tracking trade-off | `scripts/export_energy_table.py` (two-wing field model, placeholder tower ratings) | `data/tower_dallas_daily_kwh.csv` (clear sky, Dallas, derived numbers only) |
| DFW weather (Iowa Mesonet ASOS, station DFW) | Fleet wind and temperature | `scripts/fetch_data.py` | Synthetic DFW-shaped weather until fetched |
| DuraMAT emulated single-axis tracker faults (Sandia/Utah CFV Labs, 27.9 MiB parquet: tilt, motor current, stall faults) | Anchor the drive model's motor-current baseline; detect a real stall | Browser download | Not yet used — first thing to wire in if time allows |
| NASA IMS bearings (run-to-failure) | Shape of the bearing health index | `scripts/fetch_data.py --all` (~1 GB) | Shape only (exponential growth after onset) |
| CWRU bearings (drive end SKF 6205; fault frequencies x shaft speed: inner 5.415, outer 3.585, ball 2.357, cage 0.398) | Vibration Detective stretch | Case Western bearing data centre | Not used |
| EDP Wind Farm 1 with 28 confirmed failures (Mendeley, CC BY 4.0, 173.7 MB) | Real fleet anomaly → work order demo | Browser download | Not used |
| JUST slewing-bearing vibration + AE (Mendeley, CC BY 4.0) | Low-speed slewing-bearing signatures | Browser download | Not used |
| Kaggle "Industrial Machine Downtime" (2,500 rows, 3 machines, 16 columns, binary Downtime) | Optional second mill | Kaggle | Not used |

No open dataset with labelled slew-drive or yaw-drive failures was found; the tower fleet is simulated and
labelled as such.
