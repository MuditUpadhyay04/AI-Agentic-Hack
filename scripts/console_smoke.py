"""Click through the operator console without a browser, over Shiny's websocket protocol.

    shiny run app/app.py --port 8765 &
    python scripts/console_smoke.py --port 8765

Sends the same input changes a browser would (button clicks are counters), and fails if any output
reports an error. Used in CI-style checks before each zip.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys

import websockets

PLOTS = ["mill_signals", "mill_envelope", "fleet_map", "tower_chart", "tower_options_plot", "tower_energy_plot",
         "kaizen_lots", "kaizen_futures"]
UIS = ["mill_status", "mill_transcript", "mill_approval", "mill_incident", "mill_stats", "mill_wo", "mill_health",
       "plant_chip", "crew_list", "alert_badge", "alert_stats", "incident_badge", "incident_stats", "incident_table", "incident_detail", "alert_list", "alert_detail", "tower_transcript", "tower_option_cards", "tower_approval",
       "kaizen_tiles", "kaizen_rules", "kaizen_transcript", "kaizen_dcr", "grow_passport", "grow_transcript",
       "slot_buttons"]

STEPS = [
    ("mill_change", {"mill_change": 1}, ["mill_status", "mill_signals", "mill_incident", "alert_list"]),
    ("alert_escalate", {"alert_escalate": 1}, ["alert_detail", "alert_stats"]),
    ("alert_ack", {"alert_ack": 1}, ["alert_detail", "alert_badge"]),
    ("mill_assess", {"mill_assess": 1}, ["mill_transcript", "mill_approval", "mill_envelope"]),
    ("mill_pick_stop", {"mill_pick": "stop_now"}, ["mill_approval", "mill_envelope"]),
    ("mill_pick_lc", {"mill_pick": "lift_and_coast"}, ["mill_approval"]),
    ("mill_approve", {"mill_approve": 1}, ["mill_transcript", "mill_wo", "mill_incident", "mill_stats"]),
    ("mill_revert", {"mill_revert": 1}, ["mill_transcript", "mill_approval"]),
    ("mill_approve_2", {"mill_approve": 2}, ["incident_table", "incident_detail", "incident_stats"]),
    ("incident_sel", {"incident_sel": "INC-209"}, ["incident_detail"]),
    ("tower_assess", {"tower_assess": 1}, ["tower_transcript", "tower_approval"]),
    ("tower_approve", {"tower_approve": 1}, ["tower_transcript", "tower_approval"]),
    ("kaizen_run", {"kaizen_run": 1}, ["kaizen_transcript", "kaizen_dcr", "kaizen_rules"]),
    ("grow_read_tower", {"manual": "janta_tower_drive_public.md", "grow_read": 1}, ["grow_passport", "slot_buttons"]),
    ("install_ae", {"install_ae": 1}, ["slot_buttons", "grow_transcript"]),
    ("tower_42", {"tower_id": "42", "tower_assess": 2}, ["tower_transcript", "tower_chart"]),
    ("grow_sign", {"grow_sign": 1}, ["grow_passport", "grow_transcript"]),
]


async def run(port: int) -> int:
    init = {".clientdata_url_protocol": "http:", ".clientdata_url_hostname": "localhost",
            ".clientdata_url_port": str(port), ".clientdata_url_pathname": "/", ".clientdata_url_search": "",
            ".clientdata_url_hash_initial": "", ".clientdata_url_hash": "", ".clientdata_pixelratio": 1,
            ".clientdata_singletons": "", ".clientdata_allowDataUriScheme": True,
            "tower_id": "7", "manual": "lathe_l2_manual.md"}
    for p in PLOTS:
        init[f".clientdata_output_{p}_width"] = 760
        init[f".clientdata_output_{p}_height"] = 300
        init[f".clientdata_output_{p}_hidden"] = False
    for u in UIS:
        init[f".clientdata_output_{u}_hidden"] = False
    for b in ["mill_change", "mill_assess", "mill_reset", "tower_assess", "kaizen_run", "grow_read", "grow_sign"]:
        init[b] = 0
    seen: dict = {}
    errors: dict = {}
    async with websockets.connect(f"ws://127.0.0.1:{port}/websocket/", max_size=2 ** 26) as ws:
        await ws.send(json.dumps({"method": "init", "data": init}))

        async def drain(seconds: float):
            end = asyncio.get_event_loop().time() + seconds
            while True:
                left = end - asyncio.get_event_loop().time()
                if left <= 0:
                    return
                try:
                    msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=left))
                except asyncio.TimeoutError:
                    return
                for k, v in (msg.get("values") or {}).items():
                    seen[k] = v
                for k, v in (msg.get("errors") or {}).items():
                    errors[k] = v

        await drain(15)
        print(f"initial outputs: {sorted(seen)}")
        for name, data, want in STEPS:
            await ws.send(json.dumps({"method": "update", "data": data}))
            before = set(seen)
            await drain(8)
            got = [w for w in want if w in seen]
            print(f"{name:>16}: outputs {got} {'(new: ' + ', '.join(sorted(set(seen) - before)) + ')' if set(seen) - before else ''}")
    if errors:
        print("ERRORS:", json.dumps(errors, indent=1)[:3000])
        return 1
    must = ["mill_approval", "tower_approval", "kaizen_dcr", "grow_passport"]
    missing = [m for m in must if m not in seen]
    if missing:
        print("MISSING:", missing)
        return 1
    txt = json.dumps(seen.get("tower_transcript", ""))
    print("tower 42 transcript mentions acoustic:", "acoustic" in txt)
    print("OK")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    sys.exit(asyncio.run(run(ap.parse_args().port)))
