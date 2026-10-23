# Datasets

| Dataset | Used for | Access | Status in repo |
|---|---|---|---|
| AI4I 2020 (UCI 601), 10,000 rows, CC BY 4.0 | Mill walls; Matthew's failure model (trained on it; copy in `failure_model/ai4i2020.csv`); the equipment fleet's readings | `scripts/fetch_data.py` | Seeded replica from the published rules until the real file is fetched; every output names its source |
| Kaggle "Industrial Machine Downtime" (2,500 rows, 3 machines, 16 columns, binary Downtime) | Optional second mill | Kaggle | Not used |

The equipment fleet (dicing saws, wire bonders, test handlers, probers), hubs, prices and lifelines are
placeholders; each machine's sensor reading is a real AI4I record. Hari's machine-downtime model was trained on
the Kaggle "Machine Downtime" set.
