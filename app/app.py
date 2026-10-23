"""PitCrew operator console (Shiny for Python).

    shiny run app/app.py --port 8000          # then open the port (VS Code web: the Ports tab)

Run -> Improve -> Grow, with the approval card between the crew and the machine. The Run · Mill page is laid
out like an asset page in a maintenance product: incident banner, stat strip, signals, the crew's activity
log, the foreman's decision and the resulting work order. Alerts shows what the Comms agent sent the floor.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402
from shiny import App, reactive, render, ui  # noqa: E402

from pitcrew import __version__, mill, viz  # noqa: E402
from pitcrew.crew import Crew  # noqa: E402
from pitcrew.decide import diagnose, energy_table  # noqa: E402
from pitcrew.ops import ALERT_POLICY  # noqa: E402
from pitcrew.passport import manuals  # noqa: E402
from pitcrew.tower import Fleet  # noqa: E402
from pitcrew.world import World  # noqa: E402

SHARED_FLEET = Fleet().run()  # deterministic; shared read-only by every session
MILL_ROWS = mill.creep_scenario()
MODE = os.environ.get("PITCREW_LLM", "offline")
MODE_LABEL = {"offline": "Crew offline (deterministic narration)", "bedrock":
              f"Crew on Bedrock · {os.environ.get('PITCREW_MODEL_ID', 'default model')}",
              "scripted": "Crew: Strands + scripted model"}.get(MODE, MODE)
MIN_PER_PART = 4
INCIDENT = "INC-212"
FONTS = ("https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Titillium+Web:ital,wght@"
         "0,600;0,700;0,900;1,700;1,900&family=JetBrains+Mono:wght@400;500&display=swap")

# Agent -> (driver-tag code, team colour) for the activity log and the sidebar.
AGENTS = {"Sentinel": ("SEN", "#9A9DAA"), "Diagnostician": ("DIA", "#FFB800"), "Race Engineer": ("RAC", "#4D7CFE"),
          "Comms": ("COM", "#8E5CF6"), "Quartermaster": ("QMS", "#00A651"), "Dispatcher": ("DSP", "#00A651"),
          "Foreman": ("FMN", "#15151E"), "Kaizen": ("KZN", "#00A651"), "Onboarder": ("ONB", "#00A651"),
          "System": ("SYS", "#9A9DAA")}
VERBS = {"Sentinel": "checked the limits", "Diagnostician": "added a finding", "Race Engineer": "proposed an action",
         "Comms": "alerted the floor", "Quartermaster": "handled parts", "Dispatcher": "booked the work",
         "Foreman": "decided", "Kaizen": "reviewed history", "Onboarder": "onboarded an asset", "System": "note"}

# Earlier alerts today, so the Alerts page reads like a working inbox (simulated plant).
ALERT_HISTORY = [
    {"id": "AL-H02", "ref": "PO-7709", "severity": "External", "to": ["Tooling Supply Co."],
     "subject": "Request for quote: 10 x INSERT-CNMG-L, needed by Monday", "status": "needs approval",
     "sent_at": None, "channel": "Email", "body": "Please confirm price and delivery for 10 carbide inserts, part "
     "INSERT-CNMG-L, to the Austin plant by Monday.", "checks": ["Unit price", "Ship date", "Lot number on the slip"],
     "escalate_after_min": None, "rule": ALERT_POLICY["External"]},
    {"id": "AL-H01", "ref": "Tower 7", "severity": "SEV-3", "to": ["Field technician (DFW route)"],
     "subject": "[SEV-3] Tower 7 drive friction up 33%. Re-grease on the Thursday route", "status": "acknowledged",
     "sent_at": "10:05:12", "acked_at": "10:22:03", "acked_by": "Field technician", "channel": "Daily digest",
     "body": "Tower 7 (lot B grease) needs 33% more energy per degree than a healthy drive. Parked at 180 deg until "
     "the visit.", "checks": ["Bring GREASE-KIT-SD (reserved)", "Check the drive seals", "Record the failure mode"],
     "escalate_after_min": None, "rule": ALERT_POLICY["SEV-3"]},
]

ICON = {
    "assets": '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
              'aria-hidden="true"><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="3"/></svg>',
    "towers": '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
              'aria-hidden="true"><path d="M12 3v18M7 21h10M5 8h14l-2 5H7z"/></svg>',
    "alerts": '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
              'aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/></svg>',
    "improve": '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
               'aria-hidden="true"><path d="M3 3v18h18"/><path d="m7 15 4-4 3 3 5-6"/></svg>',
    "grow": '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
            'aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg>',
    "why": '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
           'aria-hidden="true"><rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 8h6M9 12h6M9 16h4"/></svg>',
    "arch": '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
            'aria-hidden="true"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/>'
            '<rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>',
}
CHECKER = ('<svg width="26" height="26" viewBox="0 0 26 26" aria-hidden="true"><rect width="13" height="13" fill="#fff"/>'
           '<rect x="13" y="13" width="13" height="13" fill="#fff"/><rect x="13" width="13" height="13" fill="#15151E" '
           'stroke="#fff"/><rect y="13" width="13" height="13" fill="#15151E" stroke="#fff"/></svg>')
ICON["incidents"] = ('<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
                     'aria-hidden="true"><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 '
                     '0-3.4 0z"/><path d="M12 9v4M12 17h.01"/></svg>')
# Closed incidents from earlier today, so the list reads like a working plant (simulated).
INCIDENT_HISTORY = [
    {"id": "INC-209", "asset": "Tower 7", "summary": "Drive friction up 33% (lot B grease); parked at 180 deg until "
     "the Thursday route", "severity": "SEV-3", "status": "MITIGATED", "opened": "10:04", "owner": "Race Engineer",
     "linked": ["AL-H01", "WO-4102"], "page": "towers", "chain": [
         ("10:04", "Sentinel", "Detect", "Friction alarm on Tower 7: +33% energy per degree"),
         ("10:05", "Comms", "Notify", "SEV-3 email to the DFW field technician"),
         ("10:05", "Diagnostician", "Analyze", "Grease breakdown, supplier lot B"),
         ("10:06", "Race Engineer", "Plan", "Park & Price: park at 180 deg for $3 of energy"),
         ("10:21", "Foreman", "Approve", "Approved: park until the visit"),
         ("10:22", "Dispatcher", "Execute", "WO-4102 on the Thursday route, 6 towers batched")]},
    {"id": "INC-207", "asset": "VM-03", "summary": "Coolant filter clogging; filter replaced", "severity": "SEV-3",
     "status": "RESOLVED", "opened": "07:41", "owner": "Dispatcher", "linked": ["WO-4087"], "page": None, "chain": [
         ("07:41", "Sentinel", "Detect", "Process temperature gap narrowing on VM-03"),
         ("07:44", "Diagnostician", "Analyze", "Coolant flow low: filter clogging"),
         ("08:02", "Foreman", "Approve", "Approved filter change at break"),
         ("09:12", "Dispatcher", "Execute", "WO-4087 closed; failure mode recorded: clogging")]},
]
NAV = [("mill", "Assets · VM-07", "assets"), ("towers", "Janta towers", "towers"),
       ("incidents", "Incidents", "incidents"), ("alerts", "Alerts", "alerts"),
       ("improve", "Improve", "improve"), ("grow", "Onboard asset", "grow"), ("why", "Why (press release)", "why"),
       ("arch", "Architecture", "arch")]


def new_world() -> World:
    w = World()
    w.__dict__["fleet"] = SHARED_FLEET
    return w


# ------------------------------------------------------------------ small UI helpers
def md_inline(text: str) -> str:
    t = html.escape(text or "")
    parts = t.split("**")
    return "".join(f"<b>{p}</b>" if i % 2 else p for i, p in enumerate(parts))


def tag(agent: str):
    code, color = AGENTS.get(agent, (agent[:3].upper(), "#9A9DAA"))
    return ui.span(ui.span(class_="bar", style=f"background:{color}"), ui.span(ui.span(code), class_="code"), class_="tag")


def skew(text, cls: str):
    return ui.span(ui.span(text), class_=f"skew {cls}")


def clock(t: float | None) -> str:
    return dt.datetime.fromtimestamp(t).strftime("%H:%M") if t else ""


def transcript(turns: list[dict], idle: str = "The crew is idle."):
    """The crew's activity log: driver tag, who did what, what they said, and the tool calls behind it."""
    if not turns:
        return ui.p(idle, class_="idle")
    items = []
    for t in turns:
        chips = []
        for x in t.get("tools", []):
            args = ", ".join(f"{k}={v}" for k, v in (x.get("args") or {}).items() if k not in ("evidence", "parts", "body"))
            body = json.dumps(x.get("result"), indent=1, default=str)
            chips.append(ui.tags.details(ui.tags.summary(ui.span(f"{x['tool']}({args})", class_="chip")),
                                         ui.tags.pre(body[:4000]), class_="tool"))
        when = clock(t["tools"][0]["t"]) if t.get("tools") else t.get("time", "")
        evidence = ui.tags.details(ui.tags.summary(f"Evidence · {len(chips)} tool call{'s' if len(chips) != 1 else ''}"),
                                   *chips) if chips else None
        items.append(ui.tags.li(
            ui.div(tag(t["agent"])),
            ui.div(ui.div(ui.tags.b(t["agent"]), ui.span(t.get("verb") or VERBS.get(t["agent"], "")),
                          ui.span(when, class_="t"), class_="top"),
                   ui.div(ui.HTML(md_inline(t["say"])), class_="say"), evidence)))
    return ui.tags.ol(*items, class_="act")


def options_table(options: list[dict], rec_key: str, kind: str):
    if kind == "mill":
        head = ["Option", "Expected cost", "Risk before window", "What it means"]
        rows = [(o["title"], f"${o['cost_usd']:,.0f}", f"{100 * o['p_fail_before_window']:.0f}%", o["detail"])
                for o in options]
    else:
        head = ["Option", "Expected cost", "Risk before visit", "Energy given up"]
        rows = [(o["title"], f"${o['expected_cost_usd']:,.0f}", f"{100 * o['p_fail']:.0f}%",
                 f"{o['energy_lost_kwh']:.0f} kWh (${o['energy_lost_usd']:.2f})") for o in options]
    keys = [o["key"] for o in options]
    trs = [ui.tags.tr(*[ui.tags.td(c) for c in r], class_="rec" if k == rec_key else "") for r, k in zip(rows, keys)]
    return ui.tags.table(ui.tags.thead(ui.tags.tr(*[ui.tags.th(h) for h in head])), ui.tags.tbody(*trs),
                         class_="opts")


def tile(num: str, lbl: str):
    return ui.div(ui.div(num, class_="num"), ui.div(lbl, class_="lbl"), class_="tile")


def stat(label: str, value: str, unit: str, sub: str, color: str, pct: float, warn: bool = False):
    on = round(pct / 10)
    segs = [ui.tags.i(style=f"background:{color}" if i < on else None) for i in range(10)]
    return ui.div(ui.div(label, class_="l"),
                  ui.div(ui.tags.b(value, class_="warn" if warn else None), ui.span(unit), class_="v"),
                  ui.div(*segs, class_="segs"), ui.div(sub, class_="s"), class_="stat")


def box(title: str, *body, note: str = "", right=None, pad: bool = False):
    hd = ui.div(ui.h2(title), ui.span(note, class_="note") if note else None,
                ui.span(right, class_="right") if right is not None else None, class_="hd")
    return ui.div(hd, ui.div(*body, class_="bd") if pad else ui.div(*body), class_="box")


def topbar(crumb: str, *extra):
    return ui.div(ui.span(ui.HTML(crumb), class_="crumb"), *extra, ui.span(class_="grow"),
                  skew(MODE_LABEL, "mode live" if MODE == "bedrock" else "mode off"), class_="topbar")


def pagehead(kicker: str, title: str, sub: str):
    return ui.div(ui.div(kicker, class_="kicker"), ui.h1(title), ui.div(sub, class_="sub"), class_="pagehead")


# ------------------------------------------------------------------ layout
def sidebar():
    links = []
    for key, label, icon in NAV:
        badge = (ui.output_ui("alert_badge", inline=True) if key == "alerts"
                 else ui.output_ui("incident_badge", inline=True) if key == "incidents" else None)
        links.append(ui.input_action_button(f"nav_{key}", ui.TagList(ui.span(class_="tick"), ui.HTML(ICON[icon]),
                                                                       ui.span(label), badge),
                                            class_="navlink" + (" active" if key == "mill" else "")))
    return ui.tags.aside(
        ui.div(ui.HTML(CHECKER), ui.div(ui.div("PITCREW", class_="word"), ui.div("Austin Plant", class_="plant")),
               class_="logo"),
        ui.tags.nav(*links, **{"aria-label": "Main"}),
        ui.div("CREW", class_="sec"),
        ui.output_ui("crew_list"),
        ui.div(ui.span("FM", class_="av"), ui.div(ui.div("Foreman", style="font-weight:600;font-size:13px"),
                                                  ui.div("Line 2 · Shift B", class_="plant")), class_="me"),
        class_="side")


def mill_page():
    return ui.nav_panel(
        "mill",
        topbar("Assets / Line 2 / <b>VM-07</b>", ui.output_ui("plant_chip", inline=True)),
        ui.div(
            ui.div(ui.div(ui.div("LINE 2 · CNC VERTICAL MILL · VARIANT L", class_="kicker"),
                          ui.div(ui.h1("VM-07"), ui.output_ui("mill_health", inline=True),
                                 style="display:flex;flex-wrap:wrap;align-items:center;gap:12px;margin-top:2px"),
                          ui.div("Insert CNMG, 120 min in use · walls from the AI4I 2020 failure rules (UCI 601)",
                                 class_="sub"), style="flex:1 1 360px;min-width:0"),
                   ui.div(ui.tags.button("Open manual", class_="btn-quiet", type="button"),
                          ui.tags.button("New work order", class_="btn-quiet", type="button"),
                          style="display:flex;gap:8px"), class_="asset-h"),
            ui.div(ui.span("Overview", class_="on"), ui.span("Signals"), ui.span("Work orders"), ui.span("Passport"),
                   class_="tabs"),
            ui.output_ui("mill_incident"),
            ui.output_ui("mill_stats"),
            ui.div(
                ui.div(box("Spindle power", ui.output_plot("mill_signals", height="270px"),
                           note="kW · one point per part · warn band above 8.1"),
                       box("Operating envelope", ui.output_plot("mill_envelope", height="330px"),
                           note="torque vs speed · the walls close in as the tool wears"),
                       class_="col-main"),
                ui.div(box("Activity", ui.output_ui("mill_transcript"), right=INCIDENT), class_="col-side"),
                class_="row2"),
            ui.output_ui("mill_approval"),
            ui.output_ui("mill_wo"),
            ui.div(ui.tags.b("Demo controls"),
                   ui.input_action_button("mill_change", "1 · Harder steel lot arrives"),
                   ui.input_action_button("mill_assess", "2 · Crew: assess and plan"),
                   ui.input_action_button("mill_reset", "Reset to normal window"),
                   ui.output_ui("mill_status", inline=True), class_="democtl"),
            class_="page"))


def towers_page():
    return ui.nav_panel(
        "towers",
        topbar("Assets / <b>Janta TR-08 fleet</b>"),
        ui.div(
            pagehead("48 TR-08 TOWERS · THREE DFW SITES · SIMULATED DRIVE MODEL", "Janta towers",
                     "Park & Price: the same crew on a different machine, priced with the Shadow Calculator energy model."),
            ui.layout_columns(
                ui.div(
                    ui.card(ui.card_header("Fleet"), ui.output_plot("fleet_map", height="300px")),
                    ui.card(ui.card_header("Selected tower"), ui.output_plot("tower_chart", height="300px")),
                    ui.output_ui("tower_option_cards"),
                ),
                ui.div(
                    ui.card(ui.card_header("Demo"),
                            ui.input_select("tower_id", "Tower", choices={"7": "Tower 7 · grease, supplier lot B",
                                                                           "19": "Tower 19 · seal leak",
                                                                           "31": "Tower 31 · backlash",
                                                                           "42": "Tower 42 · bearing (needs a future sensor)"}),
                            ui.div(ui.input_action_button("tower_assess", "Crew: assess and price options",
                                                          class_="btn-primary"), class_="step-btns"),
                            ui.p("Keep tracking, coast, park at the best azimuth or send a technician tomorrow - each "
                                 "priced with the energy model and a weather Monte Carlo of the drive.",
                                 class_="small-note")),
                    ui.card(ui.card_header("Activity"), ui.output_ui("tower_transcript")),
                    ui.output_ui("tower_approval"),
                ),
                col_widths=[7, 5]),
            class_="page"))


def incidents_page():
    return ui.nav_panel(
        "incidents",
        topbar("<b>Incidents</b>"),
        ui.div(
            pagehead("PLANT-WIDE · TODAY", "Incidents",
                     "Every incident the crew opened, who owns it, and the full chain from detection to the work "
                     "order. Times come from the tool trace."),
            ui.output_ui("incident_stats"),
            box("Incidents", ui.output_ui("incident_table"), right="click a row for its chain"),
            ui.output_ui("incident_detail"),
            class_="page"))


def alerts_page():
    return ui.nav_panel(
        "alerts",
        topbar("<b>Alerts</b>"),
        ui.div(
            pagehead("COMMS AGENT · EMAIL AND SMS TO THE FLOOR", "Operator alerts",
                     "When the crew opens an incident, Comms tells the right operator what to check, tracks the "
                     "acknowledgment, and escalates if nobody answers. Email is simulated in this prototype."),
            ui.output_ui("alert_stats"),
            ui.div(
                ui.div(box("Today", ui.output_ui("alert_list")), class_="col-side"),
                ui.div(ui.output_ui("alert_detail"), class_="col-main"),
                class_="row2"),
            box("Alert rules", ui.HTML(pd.DataFrame(
                [(k, v["who"], v["channel"], v["sends"], v["escalate"]) for k, v in ALERT_POLICY.items()],
                columns=["Severity", "Who", "Channel", "Sends", "Escalate if no ack"]).to_html(
                    index=False, classes="opts", border=0)), right="set by the operations manager · Comms follows them",
                pad=True),
            class_="page"))


def improve_page():
    return ui.nav_panel(
        "improve",
        topbar("<b>Improve</b>"),
        ui.div(
            pagehead("KAIZEN · WEEKLY", "Improve", "Rules found in data, supplier lots, Sensor Futures and the next "
                     "tower's design changes."),
            ui.layout_columns(
                ui.div(
                    ui.card(ui.card_header("Kaizen"),
                            ui.input_action_button("kaizen_run", "Run the Kaizen agent", class_="btn-primary"),
                            ui.output_ui("kaizen_tiles")),
                    ui.card(ui.card_header("Rules found in AI4I vs the published walls"), ui.output_ui("kaizen_rules")),
                    ui.card(ui.card_header("Failure rate by supplier lot"), ui.output_plot("kaizen_lots", height="280px")),
                    ui.card(ui.card_header("Sensor Futures"), ui.output_plot("kaizen_futures", height="290px")),
                ),
                ui.div(
                    ui.card(ui.card_header("Activity"), ui.output_ui("kaizen_transcript")),
                    ui.card(ui.card_header("Design-change request for TR-09 (draft)"), ui.output_ui("kaizen_dcr")),
                ),
                col_widths=[7, 5]),
            class_="page"))


def grow_page():
    return ui.nav_panel(
        "grow",
        topbar("<b>Onboard asset</b>"),
        ui.div(
            pagehead("ONBOARDER · PER MACHINE", "Onboard an asset", "Manual -> passport with future hardware slots -> "
                     "a human signs -> the agents start."),
            ui.layout_columns(
                ui.div(
                    ui.card(ui.card_header("Onboard a machine from its manual"),
                            ui.input_select("manual", "Manual", choices=manuals(), selected="lathe_l2_manual.md"),
                            ui.div(ui.input_action_button("grow_read", "Onboarder: read it", class_="btn-primary"),
                                   ui.input_action_button("grow_sign", "Sign the passport", class_="btn-success"),
                                   class_="step-btns"),
                            ui.output_ui("grow_passport")),
                ),
                ui.div(
                    ui.card(ui.card_header("Activity"), ui.output_ui("grow_transcript")),
                    ui.card(ui.card_header("Future hardware slots"),
                            ui.p("Signals the manual lists as not fitted become slots: the agents that need them "
                                 "already exist and switch on the day the sensor is installed. Try it on the Janta "
                                 "tower: install the acoustic-emission slot, then look at Tower 42.",
                                 class_="small-note"),
                            ui.output_ui("slot_buttons")),
                ),
                col_widths=[7, 5]),
            class_="page"))


def story_page():
    pr = (ROOT / "docs" / "PRFAQ.md").read_text()
    return ui.nav_panel("why", topbar("<b>Why</b>"), ui.div(ui.card(ui.markdown(pr)), class_="page"))


def arch_page():
    svg = (ROOT / "docs" / "architecture.svg").read_text()
    table = pd.DataFrame([
        ("Agents", "Strands Agents SDK, Graph for Run (fixed order, repeatable), single agents for Improve/Grow"),
        ("Runtime", "Amazon Bedrock AgentCore Runtime (agentcore/agent.py)"),
        ("Tools", "AgentCore Gateway exposing the World tools as MCP; CMMS via OpenAPI (MaintainX pattern)"),
        ("Guardrails", "AgentCore Policy (Cedar): POs over $500 and every setpoint change need the foreman"),
        ("Comms", "Alerts to the floor by policy (SEV-1/2/3); Amazon SES for email in AWS, simulated here"),
        ("Knowledge", "Bedrock Knowledge Base over manuals; AgentCore Memory for incidents; passports in S3"),
        ("Suppliers", "A2A: supplier agents on their own runtimes (agentcore/supplier_a2a.py)"),
        ("Energy", "Table exported from the Janta Shadow Calculator field model (scripts/export_energy_table.py)"),
        ("Data", "AI4I 2020 (UCI 601); tower drive model anchored to DuraMAT tracker motor current, NASA IMS"),
    ], columns=["Piece", "On AWS"])
    return ui.nav_panel("arch", topbar(f"<b>Architecture</b> · v{__version__}"),
                        ui.div(ui.card(ui.HTML(svg)),
                               ui.card(ui.HTML(table.to_html(index=False, classes="opts", border=0))), class_="page"))


NAV_JS = """
$(document).on('click', '.side .navlink', function () {
  $('.side .navlink').removeClass('active'); $(this).addClass('active');
});
$(document).on('change', 'input[name=mill_pick]', function () {
  Shiny.setInputValue('mill_pick', this.value, {priority: 'event'});
});
$(document).on('click', '.alist button', function () {
  Shiny.setInputValue('alert_sel', $(this).data('id'), {priority: 'event'});
});
$(document).on('click', 'tr.inc-row', function () {
  Shiny.setInputValue('incident_sel', $(this).data('id'), {priority: 'event'});
});
$(document).on('click', '.goto', function () {
  var k = $(this).data('page'); $('#nav_' + k).trigger('click');
});
"""

app_ui = ui.page_fluid(
    ui.head_content(ui.tags.link(rel="stylesheet", href=FONTS), ui.tags.title("PitCrew"),
                    ui.include_css(ROOT / "app" / "www" / "styles.css"), ui.tags.script(NAV_JS)),
    ui.div(sidebar(),
           ui.tags.main(ui.div(class_="redline"),
                        ui.navset_hidden(mill_page(), towers_page(), incidents_page(), alerts_page(), improve_page(), grow_page(),
                                         story_page(), arch_page(), id="page"),
                        class_="mainpane"),
           class_="shell"),
)


# ------------------------------------------------------------------ server
def server(input, output, session):
    w = new_world()
    crew = Crew(w, MODE)
    mill_step = reactive.value(0)  # 0 normal, 1 changed, 2 planned, 3 approved, 4 rejected
    mill_plan = reactive.value(None)
    mill_exec = reactive.value(None)
    mill_comms = reactive.value(None)
    mill_extra = reactive.value([])  # foreman turns the console records itself (reject, revert)
    mill_t0 = reactive.value(None)  # when the sensor story changed
    pick = reactive.value(None)
    alerts_rev = reactive.value(0)
    alert_sel = reactive.value(None)
    incident_sel = reactive.value(None)
    tower_plan = reactive.value(None)
    tower_exec = reactive.value(None)
    kaizen = reactive.value(None)
    grow = reactive.value({"turns": [], "passport": None})
    slots_rev = reactive.value(0)  # bumps when a future hardware slot is installed

    # ---------------- navigation
    for key, _, _ in NAV:
        def _bind(k=key):
            @reactive.effect
            @reactive.event(input[f"nav_{k}"])
            def _():
                ui.update_navset("page", selected=k)
        _bind()

    def live_alerts() -> list[dict]:
        alerts_rev()
        return list(reversed(w.alerts)) + ALERT_HISTORY

    @render.ui
    def alert_badge():
        n = sum(a["status"] in ("awaiting ack", "escalated", "needs approval") for a in live_alerts())
        return ui.span(str(n), class_="badge-n hot" if n else "badge-n")

    @render.ui
    def crew_list():
        alerts_rev()
        s = mill_step()
        waiting = any(a["status"] in ("awaiting ack", "escalated") for a in w.alerts)
        busy = {"Sentinel": s == 1, "Race Engineer": s == 2, "Comms": waiting}
        rows = [ui.div(tag(a), ui.span(a), ui.span(class_="dot busy" if busy.get(a) else "dot"), class_="crew-row")
                for a in ["Sentinel", "Diagnostician", "Race Engineer", "Comms", "Quartermaster", "Dispatcher"]]
        return ui.div(*rows, style="padding:8px 0")

    # ---------------- mill: numbers the page shows, all from the same mill functions the tools use
    def mill_numbers() -> dict:
        s = mill_step()
        st = dict(w.mill_state)
        if s == 0:
            st.update(torque=40.0, d_temp=10.2, creep=0.0)
        kw = st["torque"] * mill.omega(st["rpm"]) / 1000
        n, _ = mill.parts_until_wall(st["rpm"], st["torque"], st["wear"], st["d_temp"], st["creep"], st["variant"])
        t0 = mill_t0() or dt.datetime.now()
        return {"kw": kw, "parts": n, "rpm": st["rpm"], "torque": st["torque"], "wear": st["wear"],
                "limit_at": (t0 + dt.timedelta(minutes=MIN_PER_PART * n)).strftime("%H:%M"),
                "window_at": (t0 + dt.timedelta(minutes=MIN_PER_PART * st["parts_to_window"])).strftime("%H:%M"),
                "window_parts": st["parts_to_window"], "opened": t0.strftime("%H:%M")}

    def chosen() -> dict | None:
        p = mill_plan()
        if not p:
            return None
        k = pick() or p["recommendation"]["key"]
        return next((o for o in p["options"] if o["key"] == k), p["recommendation"])

    def reset_mill():
        nonlocal w, crew
        w = new_world()
        crew = Crew(w, MODE)
        for v, x in ((mill_step, 0), (mill_plan, None), (mill_exec, None), (mill_comms, None), (mill_extra, []),
                     (mill_t0, None), (pick, None), (alert_sel, None)):
            v.set(x)
        alerts_rev.set(alerts_rev() + 1)

    @reactive.effect
    @reactive.event(input.mill_reset)
    def _():
        reset_mill()

    @reactive.effect
    @reactive.event(input.mill_change)
    def _():
        if mill_step() >= 1:
            return
        mill_t0.set(dt.datetime.now())
        mill_step.set(1)
        mill_comms.set(crew.alert_mill())  # Comms emails the floor as soon as the story changes
        alerts_rev.set(alerts_rev() + 1)

    @reactive.effect
    @reactive.event(input.mill_assess)
    def _():
        if mill_step() < 1:
            mill_t0.set(dt.datetime.now())
            mill_step.set(1)
            mill_comms.set(crew.alert_mill())
            alerts_rev.set(alerts_rev() + 1)
        with ui.Progress() as p:
            p.set(message="Crew is assessing VM-07...")
            mill_plan.set(crew.plan_mill())
        pick.set(None)
        mill_exec.set(None)
        mill_step.set(2)

    @reactive.effect
    @reactive.event(input.mill_pick)
    def _():
        pick.set(input.mill_pick())

    @reactive.effect
    @reactive.event(input.mill_approve)
    def _():
        p, c = mill_plan(), chosen()
        if p is None or mill_step() != 2:
            return
        note = (input.mill_note() or "").strip()
        mill_exec.set(crew.execute({**p, "recommendation": c}, "Foreman"))
        if note:
            mill_extra.set(mill_extra() + [{"agent": "Foreman", "verb": "left a note", "say": note, "tools": [],
                                            "time": dt.datetime.now().strftime("%H:%M")}])
        mill_step.set(3)

    @reactive.effect
    @reactive.event(input.mill_reject)
    def _():
        if mill_step() != 2:
            return
        note = (input.mill_note() or "").strip() or "No reason given."
        mill_extra.set(mill_extra() + [{"agent": "Foreman", "verb": "rejected the proposal", "tools": [],
                                        "time": dt.datetime.now().strftime("%H:%M"),
                                        "say": f"Rejected. {note} Nothing changes on the machine."}])
        mill_step.set(4)

    @reactive.effect
    @reactive.event(input.mill_replan)
    def _():
        mill_step.set(2)

    @reactive.effect
    @reactive.event(input.mill_revert)
    def _():
        if mill_step() != 3:
            return
        n0 = len(w.trace)
        w.agent = "Foreman"
        w.write_mill_setpoint(1500.0, 56.0, approved_by="Foreman")
        mill_extra.set(mill_extra() + [{"agent": "Foreman", "verb": "reverted the setpoint", "tools": w.trace[n0:],
                                        "say": "Setpoint back to 1,500 rpm / 56 Nm. The proposal is open again; the "
                                               "reserved part and booked work order stay in place."}])
        mill_exec.set(None)
        mill_step.set(2)

    @render.ui
    def plant_chip():
        s = mill_step()
        risk = 1 if s in (1, 2, 4) else 0
        return ui.span(ui.span("PLANT", class_="k"), ui.span(ui.tags.b(str(12 - risk)), " healthy"),
                       ui.span(ui.tags.b(str(risk)), " at risk", class_="risk" if risk else None),
                       ui.span(ui.tags.b(str(len(w.ops.work_orders))), " WOs today"), class_="plantchip")

    @render.ui
    def mill_health():
        s = mill_step()
        if s in (1, 2, 4):
            return skew("! AT RISK", "health risk")
        if s == 3:
            return skew("✓ PROTECTED", "health prot")
        return skew("✓ HEALTHY", "health ok")

    @render.ui
    def mill_incident():
        s = mill_step()
        if s == 0:
            return ui.div()
        n = mill_numbers()
        if s == 3:
            c = chosen()
            head = (f"VM-07 is running at {n['rpm']:,.0f} rpm until the {n['window_at']} insert change."
                    if c and c["key"] == "lift_and_coast" else f"{c['title'] if c else 'Plan'} approved for VM-07.")
            wo = (mill_exec() or {}).get("work_order") or {}
            return ui.div(ui.div("MITIGATED", class_="flag ink"),
                          ui.div(ui.div(ui.div(head, class_="head"),
                                        ui.div(f"{INCIDENT} · approved by Foreman · {wo.get('wo', '')} booked · SEV-2",
                                               class_="meta"), style="flex:1 1 320px;min-width:0"),
                                 ui.input_action_button("mill_revert", "Revert setpoint", class_="btn-quiet"),
                                 class_="body"), class_="incident", role="status")
        if s == 4:
            body = [ui.div(ui.div("Proposal rejected. VM-07 is still close to its power limit.", class_="head"),
                           ui.div(f"{INCIDENT} · nothing changed on the machine · SEV-2", class_="meta"),
                           style="flex:1 1 320px;min-width:0"),
                    ui.input_action_button("mill_replan", "Reopen the proposal", class_="btn-quiet")]
            return ui.div(ui.div("INCIDENT", class_="flag red"), ui.div(*body, class_="body"), class_="incident",
                          role="status")
        action = (ui.a("Review proposal ↓", href="#proposal", class_="cta") if s == 2
                  else ui.span("Crew is analyzing · press 2 to assess", class_="working"))
        return ui.div(ui.div("INCIDENT", class_="flag red"),
                      ui.div(ui.div(ui.div(f"VM-07 hits its power limit in about {MIN_PER_PART * n['parts']} min "
                                           f"({n['limit_at']}).", class_="head"),
                                    ui.div(f"{INCIDENT} · opened {n['opened']} by Sentinel · operator alerted by Comms"
                                           f" · SEV-2", class_="meta"), style="flex:1 1 320px;min-width:0"),
                             action, class_="body"), class_="incident", role="status")

    @render.ui
    def mill_stats():
        s, n = mill_step(), mill_numbers()
        risk = s in (1, 2, 4)
        head = 100 * (9.0 - n["kw"]) / 9.0
        red, green, ink, amber = "#E10600", "#00A651", "#15151E", "#FFB800"
        parts = "60+" if n["parts"] >= 60 else str(n["parts"])
        mins = MIN_PER_PART * n["parts"]
        return ui.div(
            stat("SPINDLE POWER", f"{n['kw']:.1f}", "of 9.0 kW", f"{head:.0f}% margin to the PWF limit",
                 red if risk else green, 100 * n["kw"] / 9.0, warn=risk),
            stat("PARTS TO LIMIT", parts, "parts",
                 f"≈ {mins} min · limit at {n['limit_at']}" if n["parts"] < 60 else "over 4 h · no limit in range",
                 red if risk else green, min(100, 100 * n["parts"] / max(n["window_parts"], 1)), warn=risk),
            stat("MAINTENANCE WINDOW", n["window_at"], "", f"shift change · {n['window_parts']} parts · "
                 f"{MIN_PER_PART * n['window_parts'] // 60} h", ink, 50),
            stat("INSERT WEAR", f"{n['wear']:.0f}", "of 200 min", "replace above 180 (manual)", amber,
                 100 * n["wear"] / 200),
            class_="stats")

    @render.plot(alt="VM-07 spindle power per part against the 9 kW limit")
    def mill_signals():
        s = mill_step()
        now = 19 if s == 0 else 21
        sp = None
        if s == 3:
            st = w.mill_state
            sp = st["torque"] * mill.omega(st["rpm"]) / 1000
        return viz.mill_signals(MILL_ROWS, now, setpoint_kw=sp)

    @render.plot(alt="Safe operating envelope in speed and torque")
    def mill_envelope():
        st = dict(w.mill_state) if mill_step() < 3 else dict(rpm=1500.0, torque=56.0, wear=120.0, d_temp=8.2,
                                                             creep=0.3, variant="L")
        if mill_step() == 0:
            st.update(torque=40.0, d_temp=10.2)
        lc = None
        c = chosen()
        if mill_step() in (2, 3) and c and c["key"] == "lift_and_coast":
            lc = {"rpm": c["rpm"], "torque": c["torque"]}
        return viz.envelope(st, lc)

    @render.ui
    def mill_status():
        msg = ["Normal window: 40 Nm, 6.3 kW, wide margins on every wall.",
               "Harder steel lot: torque 56 Nm, creeping 0.3 Nm per part.",
               "Plan ready: the foreman decides.", "Approved and executing.", "Rejected."][mill_step()]
        return ui.span(msg)

    @render.ui
    def mill_transcript():
        plan = (mill_plan() or {}).get("turns", [])
        comms = (mill_comms() or {}).get("turns", [])
        turns = plan[:1] + comms + plan[1:] + (mill_exec() or {}).get("turns", []) + mill_extra()
        return transcript(turns, "All walls clear. Sentinel checks every part; nothing to report.")

    @render.ui
    def mill_approval():
        p = mill_plan()
        if not p or mill_step() != 2:
            return ui.div()
        rec = p["recommendation"]
        st = w.mill_state
        n = mill_numbers()
        opts = []
        for o in p["options"]:
            risk = 100 * o["p_fail_before_window"]
            checked = {"checked": ""} if o["key"] == (pick() or rec["key"]) else {}
            opts.append(ui.tags.label(
                ui.tags.input(type="radio", name="mill_pick", value=o["key"], **checked),
                ui.span(ui.span(o["title"], class_="t"),
                        ui.span("RECOMMENDED", class_="rec") if o["key"] == rec["key"] else None,
                        ui.span(o["detail"], class_="d")),
                ui.span(ui.tags.b(f"${o['cost_usd']:,.0f}"), ui.span(f"risk {risk:.0f}%", class_="bad" if risk > 50 else None),
                        class_="c"), class_="opt"))
        c = chosen()

        def row(field, was, now):
            return ui.tags.tr(ui.tags.td(field), ui.tags.td(was), ui.tags.td(now))

        lc = c["key"] == "lift_and_coast"
        stop = c["key"] == "stop_now"
        diff = ui.tags.table(
            ui.tags.thead(ui.tags.tr(ui.tags.th("Field"), ui.tags.th("Current"), ui.tags.th("Proposed"))),
            ui.tags.tbody(
                row("Spindle speed", ui.span(f"{st['rpm']:,.0f} rpm", class_="was" if lc or stop else None),
                    ui.span(f"{c['rpm']:,.0f} rpm" if lc else ("stopped" if stop else "no change"),
                            class_="now" if lc or stop else "none")),
                row("Feed (torque)", ui.span(f"{st['torque']:.0f} Nm", class_="was" if lc else None),
                    ui.span(f"{c['torque']:.0f} Nm", class_="now") if lc else ui.span("no change", class_="none")),
                row("Insert change", ui.span("not planned", class_="none"),
                    ui.span(f"shift change, {n['window_at']}" if lc else ("now" if stop else "not planned"),
                            class_="now" if (lc or stop) else "none")),
                row("Part reservation", ui.span("none", class_="none"), ui.span("INSERT-CNMG-L × 1", class_="now")),
                row("Purchase order", ui.span("none", class_="none"),
                    ui.span(ui.span("drafted if stock drops below reorder", class_="now"),
                            ui.span(" · auto under the $500 policy", class_="none")))),
            class_="diff")
        a = p["assumptions"]
        return ui.div(
            ui.div(ui.div("YOUR CALL", class_="flag amber"),
                   ui.div(ui.h2(f"Proposed action: {rec['title']} until shift change"),
                          ui.span(f"from Race Engineer · {INCIDENT}", class_="m"),
                          ui.span("tool numbers only", class_="m r"), class_="txt"), class_="bandhd"),
            ui.div(ui.div(ui.h3("CHANGES IF APPROVED"), ui.div(diff, style="overflow-x:auto"),
                          ui.p(f"Why: {c['detail']} Assumptions: ${a['contribution_per_hour']:,.0f}/h lost margin, "
                               f"{a['cycle_min']:.0f} min per part, planned tool change "
                               f"{a['planned_tool_change_min']:.0f} min. Replace with the plant's numbers.",
                               class_="why"), class_="l"),
                   ui.div(ui.h3("OPTIONS COMPARED"), ui.div(*opts, role="radiogroup"),
                          ui.p("Expected cost = P(fail before the window) × unplanned stop + planned stop + slower "
                               "output. Source: price_mill_options()", class_="why"), class_="r"),
                   class_="split"),
            ui.div(ui.input_text("mill_note", "Note for the record (optional)", placeholder="e.g. hold feed on order 5521"),
                   ui.input_action_button("mill_reject", "Reject", class_="btn-reject"),
                   ui.input_action_button("mill_approve", ui.TagList("Approve ", ui.output_text("pick_title", inline=True)),
                                          class_="btn-approve"),
                   class_="decide"),
            id="proposal", class_="proposal")

    @render.text
    def pick_title():
        c = chosen()
        return c["title"] if c else ""

    @render.ui
    def mill_wo():
        e = mill_exec()
        if not e or mill_step() != 3:
            return ui.div()
        wo = e.get("work_order") or {}
        tools = [x for t in e.get("turns", []) for x in t.get("tools", [])]
        po = next((x["result"] for x in tools if x["tool"] == "draft_po"), None)
        res = next((x["result"] for x in tools if x["tool"] == "reserve_part"), {})
        st = w.mill_state
        parts = ", ".join(f"{p[0]} × {p[1]}" for p in wo.get("parts", []))
        return ui.div(
            ui.div(ui.div("SCHEDULED", class_="flag green"),
                   ui.div(ui.span(wo.get("wo", ""), class_="m", style="font-family:'JetBrains Mono',monospace"),
                          ui.h2(wo.get("title", "")),
                          ui.span(f"approved by {wo.get('approved_by') or 'Foreman'} · created by Dispatcher", class_="m r"),
                          class_="txt"), class_="bandhd"),
            ui.div(ui.div(ui.div("Asset", class_="k"), ui.div(f"{wo.get('asset', '')} · Line 2", class_="v")),
                   ui.div(ui.div("Assignee", class_="k"), ui.div(wo.get("tech", ""), class_="v")),
                   ui.div(ui.div("Due", class_="k"), ui.div(f"{wo.get('due', '')} ({mill_numbers()['window_at']})",
                                                            class_="v")),
                   ui.div(ui.div("Machine setpoint until then", class_="k"), ui.div(st["setpoint"], class_="v")),
                   class_="wo-grid"),
            ui.div(ui.div(ui.h4("CHECKLIST"),
                          ui.tags.ul(*[ui.tags.li(ui.span(class_="box-check"), x) for x in
                                       ["Lock out the spindle", *wo.get("evidence", [])[1:],
                                        "Restore the normal setpoint and record the failure mode"]])),
                   ui.div(ui.h4("PARTS AND LINKED RECORDS"),
                          ui.tags.ul(ui.tags.li(parts, ui.span(" reserved", class_="okc"),
                                                f" · {res.get('available_after', '?')} left on the shelf"),
                                     ui.tags.li(f"{po['po']} · {po['qty']} inserts · ${po['total_usd']:,.0f} · ",
                                                ui.span(po["status"], class_="okc")) if po else None,
                                     ui.tags.li(f"{INCIDENT} · evidence and agent trace attached"))),
                   class_="wo-more"),
            class_="proposal")

    # ---------------- incidents: built from the session's own state and trace, plus today's closed ones
    def live_incidents() -> list[dict]:
        alerts_rev()
        s = mill_step()
        out = []
        if s >= 1:
            trace = w.trace
            first = {}
            for x in trace:
                first.setdefault(x["agent"], clock(x["t"]))
            n = mill_numbers()
            status = {1: "OPEN", 2: "AWAITING APPROVAL", 3: "MITIGATED", 4: "OPEN"}[s]
            seen = next((x["result"] for x in trace if x["tool"] == "read_mill"), None)  # the first reading
            chain = [(n["opened"], "Sentinel", "Detect",
                      f"Power {seen['power_w'] / 1000:.1f} kW, about {seen['parts_until_wall']} parts to the PWF limit"
                      if seen else "Torque stepped up with the new steel lot")]
            a = next((x for x in w.alerts if x["ref"] == "VM-07"), None)
            if a:
                chain.append((a["sent_at"][:5], "Comms", "Notify", f"{a['severity']} email to "
                              f"{', '.join(a['to'])} · {a['status']}"))
            plan = mill_plan()
            if plan:
                rec = plan["recommendation"]
                chain.append((first.get("Diagnostician", ""), "Diagnostician", "Analyze",
                              "Dulling insert on harder stock; heat wall live below 1,380 rpm"))
                chain.append((first.get("Race Engineer", ""), "Race Engineer", "Plan",
                              f"{rec['title']}: ${rec['cost_usd']:,.0f} expected"))
            for t in mill_extra():
                chain.append((t.get("time") or (clock(t["tools"][0]["t"]) if t.get("tools") else ""), "Foreman",
                              "Decide", t["say"]))
            e = mill_exec()
            linked = [a["id"]] if a else []
            if e:
                c = chosen()
                chain.append((first.get("Foreman", ""), "Foreman", "Approve", f"Approved: {c['title'] if c else ''}"))
                for t in e.get("turns", []):
                    if t["agent"] in ("Quartermaster", "Dispatcher"):
                        chain.append((clock(t["tools"][0]["t"]) if t.get("tools") else "", t["agent"], "Execute",
                                      t["say"]))
                wo = (e.get("work_order") or {}).get("wo")
                linked += [x["result"]["po"] for t in e["turns"] for x in t.get("tools", []) if x["tool"] == "draft_po"]
                linked += [wo] if wo else []
            out.append({"id": INCIDENT, "asset": "VM-07", "summary": "Power near the PWF limit after steel lot "
                        "change" + ("; Lift & Coast to the shift change" if s == 3 else ""), "severity": "SEV-2",
                        "status": status, "opened": n["opened"],
                        "owner": {1: "Sentinel", 2: "Foreman", 3: "Dispatcher", 4: "Race Engineer"}[s],
                        "linked": linked, "page": "mill", "chain": chain})
        return out + INCIDENT_HISTORY

    @render.ui
    def incident_badge():
        n = sum(i["status"] not in ("MITIGATED", "RESOLVED") for i in live_incidents())
        return ui.span(str(n), class_="badge-n hot" if n else "badge-n")

    @reactive.effect
    @reactive.event(input.incident_sel)
    def _():
        incident_sel.set(input.incident_sel())

    def selected_incident(inc: list[dict]) -> dict | None:
        return next((i for i in inc if i["id"] == incident_sel()), inc[0] if inc else None)

    @render.ui
    def incident_stats():
        inc = live_incidents()
        open_ = [i for i in inc if i["status"] not in ("MITIGATED", "RESOLVED")]
        waiting = [i for i in inc if i["status"] == "AWAITING APPROVAL"]

        def minutes(i):  # detection to the last execute step, from the chain's clock times
            ts = [t for t, _, step, _ in i["chain"] if t and step in ("Detect", "Execute")]
            h0, m0 = map(int, ts[0].split(":"))
            h1, m1 = map(int, ts[-1].split(":"))
            return (h1 * 60 + m1) - (h0 * 60 + m0)

        closed = sorted(minutes(i) for i in inc if i["status"] in ("MITIGATED", "RESOLVED")
                        and any(step == "Execute" for _, _, step, _ in i["chain"]))
        median = str(closed[len(closed) // 2]) if closed else "—"
        return ui.div(
            stat("OPEN", str(len(open_)), "", "need attention" if open_ else "nothing open",
                 "#E10600" if open_ else "#00A651", 100 if open_ else 0, warn=bool(open_)),
            stat("AWAITING YOUR CALL", str(len(waiting)), "", "foreman approval", "#FFB800", 100 if waiting else 0),
            stat("MITIGATED / RESOLVED", str(len(inc) - len(open_)), "", "today", "#00A651",
                 100 * (len(inc) - len(open_)) / max(len(inc), 1)),
            stat("MEDIAN DETECT → WORK ORDER", median, "min", f"{len(closed)} closed incidents today", "#15151E", 40),
            class_="stats")

    @render.ui
    def incident_table():
        inc = live_incidents()
        sel = selected_incident(inc)
        cls = {"OPEN": "esc", "AWAITING APPROVAL": "wait", "MITIGATED": "ack", "RESOLVED": "sent"}
        rows = [ui.tags.tr(ui.tags.td(i["id"], style="font-family:'JetBrains Mono',monospace;font-size:12px"),
                           ui.tags.td(ui.span(i["status"], class_=f"st {cls.get(i['status'], 'sent')}")),
                           ui.tags.td(i["severity"]), ui.tags.td(ui.tags.b(i["asset"])), ui.tags.td(i["summary"]),
                           ui.tags.td(tag(i["owner"]), " ", i["owner"], style="white-space:nowrap"),
                           ui.tags.td(i["opened"]), ui.tags.td(", ".join(i["linked"]) or "—"),
                           class_="inc-row" + (" sel" if sel and i["id"] == sel["id"] else ""),
                           **{"data-id": i["id"]}) for i in inc]
        head = ["ID", "Status", "Sev", "Asset", "Summary", "Owner", "Opened", "Linked"]
        return ui.div(ui.tags.table(ui.tags.thead(ui.tags.tr(*[ui.tags.th(h) for h in head])), ui.tags.tbody(*rows),
                                    class_="opts inc"), style="overflow-x:auto;padding:4px 12px 8px")

    @render.ui
    def incident_detail():
        i = selected_incident(live_incidents())
        if not i:
            return ui.div()
        items = [ui.tags.li(ui.div(tag(agent)),
                            ui.div(ui.div(ui.tags.b(agent), ui.span(step), ui.span(t, class_="t"), class_="top"),
                                   ui.div(text, class_="say"))) for t, agent, step, text in i["chain"]]
        go = (ui.tags.button(f"Open {i['asset']}", type="button", class_="btn-quiet goto",
                             **{"data-page": i["page"]}) if i.get("page") else None)
        return box(f"{i['id']} · chain", ui.tags.ol(*items, class_="act"), go,
                   note=f"{i['asset']} · {i['severity']} · {i['status']}", pad=False)

    # ---------------- alerts
    @render.ui
    def alert_stats():
        al = live_alerts()
        waiting = [a for a in al if a["status"] in ("awaiting ack", "escalated")]
        appr = [a for a in al if a["status"] == "needs approval"]
        sent = [a for a in al if a.get("sent_at")]
        return ui.div(
            stat("SENT TODAY", str(len(sent)), "alerts", "email, SMS and digests", "#15151E", 10 * len(sent)),
            stat("AWAITING ACK", str(len(waiting)), "", "escalates by policy" if waiting else "all acknowledged",
                 "#E10600" if waiting else "#00A651", 100 if waiting else 0, warn=bool(waiting)),
            stat("ESCALATED", str(sum(a["status"] == "escalated" for a in al)), "", "to the line supervisor",
                 "#E10600", 0),
            stat("NEEDS YOUR APPROVAL", str(len(appr)), "", "external email to a supplier", "#2E5BD8", 100 if appr else 0),
            class_="stats")

    def selected_alert(al: list[dict]) -> dict | None:
        sid = alert_sel()
        return next((a for a in al if a["id"] == sid), al[0] if al else None)

    @reactive.effect
    @reactive.event(input.alert_sel)
    def _():
        alert_sel.set(input.alert_sel())

    @render.ui
    def alert_list():
        al = live_alerts()
        sel = selected_alert(al)
        sev = {"SEV-1": "#E10600", "SEV-2": "#FFB800", "SEV-3": "#9A9DAA", "External": "#4D7CFE"}
        cls = {"awaiting ack": "wait", "escalated": "esc", "acknowledged": "ack", "needs approval": "appr"}
        rows = []
        for a in al:
            rows.append(ui.tags.li(ui.tags.button(
                ui.span(class_="sev", style=f"background:{sev.get(a['severity'], '#D5D6DD')}"),
                ui.span(ui.span(ui.span(a["ref"]), ui.span(a["status"].upper(), class_=f"st {cls.get(a['status'], 'sent')}"),
                                ui.span((a.get("sent_at") or "draft")[:5], class_="t"), class_="r1"),
                        ui.span(a["subject"], class_="subj"), ui.span("To " + ", ".join(a["to"]), class_="to")),
                type="button", class_="sel" if sel and a["id"] == sel["id"] else None, **{"data-id": a["id"]})))
        return ui.tags.ul(*rows, class_="alist")

    @render.ui
    def alert_detail():
        al = live_alerts()
        a = selected_alert(al)
        if not a:
            return box("Email", ui.p("No alerts yet. Change the sensor story on VM-07 to see Comms at work.",
                                     class_="idle"), pad=True)
        live = any(x["id"] == a["id"] for x in w.alerts)
        flag = {"SEV-1": "red", "SEV-2": "amber", "SEV-3": "ink", "External": "ink"}.get(a["severity"], "ink")
        email = ui.div(
            ui.div(ui.div(a["severity"].upper(), class_=f"flag {flag}"),
                   ui.div(ui.span(a["ref"], class_="m", style="font-family:'JetBrains Mono',monospace"),
                          ui.h2(f"{a['channel']} · {a['severity']}"),
                          ui.span("written by Comms" + (f" · {a['sent_at']}" if a.get("sent_at") else " · draft"),
                                  class_="m r"), class_="txt"), class_="bandhd"),
            ui.div(ui.span("From", class_="k"), ui.span("PitCrew Comms <alerts@plant.example>"),
                   ui.span("To", class_="k"), ui.span(", ".join(a["to"])),
                   ui.span("Subject", class_="k"), ui.span(a["subject"], style="font-weight:600"), class_="mailhd"),
            ui.div(ui.p(a["body"], style="margin:0"),
                   ui.div(ui.div("PLEASE CHECK", class_="k"), ui.tags.ol(*[ui.tags.li(c) for c in a["checks"]]),
                          class_="checks"),
                   ui.div(ui.span("Acknowledge", class_="p"), ui.span("Open in PitCrew", class_="s"),
                          ui.span("buttons as the operator sees them in the email", class_="n"), class_="fakebtns"),
                   class_="mailbd"),
            class_="proposal")
        st = a["status"]
        ext = a["severity"] == "External"
        steps = [("Drafted", "done", a.get("sent_at") or "now"),
                 ("Approve to send" if ext and st == "needs approval" else "Sent",
                  "done" if a.get("sent_at") else "wait", a.get("sent_at") or "awaiting you"),
                 ("Delivered", "done" if a.get("sent_at") else "wait", a.get("sent_at") or "—"),
                 ("Escalated" if st == "escalated" else "Acknowledged",
                  "esc" if st == "escalated" else ("done" if st == "acknowledged" else "wait"),
                  a.get("escalated_at") or a.get("acked_at") or "pending")]
        step_ui = ui.tags.ol(*[ui.tags.li(ui.tags.i(class_=k if k != "wait" else None),
                                          ui.div(lbl, class_=f"lbl {k}"), ui.div(t, class_="tm")) for lbl, k, t in steps],
                             class_="steps")
        note = None
        if st == "awaiting ack" and a.get("escalate_after_min"):
            note = ui.div(f"No acknowledgment yet. Comms escalates after {a['escalate_after_min']} min: "
                          f"{a['rule']['escalate']}.", class_="escnote wait")
        elif st == "escalated":
            note = ui.div(f"Escalated at {a.get('escalated_at', '')[:5]}: {a['rule']['escalate']}.", class_="escnote esc")
        btns = ui.div(ui.input_action_button("alert_ack", "Mark acknowledged", class_="btn-approve"),
                      ui.input_action_button("alert_escalate", "Escalate now", class_="btn-reject"),
                      class_="abtns") if live and st in ("awaiting ack", "escalated") else None
        delivery = box("Delivery", step_ui, note, btns, note=f"{a['severity']} rule · {a['rule']['sends'].lower()}")
        return ui.div(email, delivery, style="display:flex;flex-direction:column;gap:20px")

    @reactive.effect
    @reactive.event(input.alert_ack)
    def _():
        a = selected_alert(live_alerts())
        if a and any(x["id"] == a["id"] for x in w.alerts):
            w.agent = "Comms"
            w.ack_alert(a["id"], "Line 2 operator")
            alerts_rev.set(alerts_rev() + 1)

    @reactive.effect
    @reactive.event(input.alert_escalate)
    def _():
        a = selected_alert(live_alerts())
        if a and any(x["id"] == a["id"] for x in w.alerts):
            w.agent = "Comms"
            w.escalate_alert(a["id"])
            alerts_rev.set(alerts_rev() + 1)

    # ---------------- towers
    @render.plot(alt="Fleet map with flagged towers")
    def fleet_map():
        slots_rev()
        ov = w.fleet_overview()
        return viz.fleet_map(SHARED_FLEET.today(), ov["flagged"], int(input.tower_id()))

    @render.plot(alt="Selected tower indicator over time")
    def tower_chart():
        slots_rev()
        tid = int(input.tower_id())
        d = diagnose(SHARED_FLEET, tid, w.installed_slots)
        if not d["primary"]:
            h = SHARED_FLEET.history(tid, 120)
            series = {"date": [x.date().isoformat() for x in h["date"]],
                      "value": (h["epd_norm"].ewm(span=7).mean() / SHARED_FLEET.baseline_epd).tolist()}
            return viz.tower_indicator(series, 1.15, 1.5, f"Tower {tid}: nothing flagged with today's sensors", None)
        p = d["primary"]
        label = {"friction": "energy per degree vs a healthy drive", "backlash": "reversal dead zone (deg)",
                 "grease_water": "water in the grease (ppm)", "acoustic": "acoustic emission (counts)"}.get(
            p["detector"], p["detector"])
        return viz.tower_indicator(d["series"], p["alarm"], p["fail_at"], f"Tower {tid}: {label}", d.get("rul"))

    @reactive.effect
    @reactive.event(input.tower_assess)
    def _():
        with ui.Progress() as p:
            p.set(message=f"Crew is assessing tower {input.tower_id()}...")
            tower_plan.set(crew.plan_tower(int(input.tower_id())))
        tower_exec.set(None)

    @reactive.effect
    @reactive.event(input.tower_approve)
    def _():
        if tower_plan() is None or not tower_plan().get("recommendation"):
            return
        tower_exec.set(crew.execute(tower_plan(), "Foreman"))

    @render.ui
    def tower_transcript():
        turns = (tower_plan() or {}).get("turns", []) + (tower_exec() or {}).get("turns", [])
        return transcript(turns)

    @render.ui
    def tower_option_cards():
        p = tower_plan()
        if not p or not p.get("options"):
            return ui.div()
        return ui.div(ui.card(ui.card_header("Park & Price"), ui.output_plot("tower_options_plot", height="250px")),
                      ui.card(ui.card_header("Energy behind the prices"), ui.output_plot("tower_energy_plot",
                                                                                          height="250px")))

    @render.plot(alt="Expected cost of each option")
    def tower_options_plot():
        p = tower_plan()
        return viz.option_risk(p["options"], p["visit_in_days"])

    @render.plot(alt="Daily energy per option over the window")
    def tower_energy_plot():
        p = tower_plan()
        start = dt.date(2026, 10, 24)
        return viz.energy_window(energy_table(), start, max(p["visit_in_days"], 2), p["energy"]["park_azimuth"])

    @render.ui
    def tower_approval():
        p = tower_plan()
        if not p or not p.get("recommendation"):
            return ui.div()
        rec = p["recommendation"]
        body = [options_table(p["options"], rec["key"], "tower"),
                ui.p(f"Failure cost ~${p['failure_cost_usd']:,.0f} (new drive, lift, regional truck roll, "
                     f"{p['economics']['drive_lead_days']} days stuck). Energy at "
                     f"${p['economics']['energy_usd_per_kwh']:.2f}/kWh. Fix: {p['fix']['title']}.",
                     class_="small-note")]
        if tower_exec():
            wo = tower_exec().get("work_order") or {}
            b = tower_exec().get("batched") or []
            body.append(ui.p(f"Approved · {wo.get('wo', '')} on {wo.get('due', '')}"
                             + (f" · {len(b)} more towers batched on the same truck roll" if b else ""),
                             class_="approved"))
        else:
            body.append(ui.input_action_button("tower_approve", f"Approve: {rec['title']}", class_="btn-approve"))
        return ui.card(ui.card_header(f"Your call: tower {p['tower_id']}"), *body, class_="approval")

    # ---------------- improve
    @reactive.effect
    @reactive.event(input.kaizen_run)
    def _():
        with ui.Progress() as p:
            p.set(message="Kaizen is mining the fleet history...")
            kaizen.set(crew.improve())

    @render.ui
    def kaizen_tiles():
        k = kaizen()
        if not k:
            return ui.p("Mines AI4I and the fleet's incident history; proposes rules, supplier actions and the "
                        "next tower's hardware.", class_="small-note")
        tr, sf = k["tracking"], k["futures"]
        b = next((x for x in k["lots"]["lots"] if x["lot"] == "B"), {})
        return ui.layout_columns(
            tile(f"{tr['energy_loss_step15_pct']}%", "energy given up by 15 deg step tracking"),
            tile(f"-{tr['starts_cut_pct']:.0f}%", "drive starts per day"),
            tile(f"{b.get('rate_ratio_vs_A', '?')}x", "lot B failure rate vs lot A"),
            tile(f"${sf['crew_value_usd_per_tower_year']:,.0f}", "per tower-year: crew acting on today's sensors"),
            col_widths=[3, 3, 3, 3])

    @render.ui
    def kaizen_rules():
        k = kaizen()
        if not k:
            return ui.div()
        df = pd.DataFrame(k["rules"]["rules"])[["mode", "rule", "published", "precision", "recall", "count"]]
        return ui.div(ui.HTML(df.to_html(index=False, classes="opts", border=0)),
                      ui.p(f"Source: {k['rules']['source']}", class_="small-note"))

    @render.plot(alt="Failures per tower-year by supplier lot")
    def kaizen_lots():
        k = kaizen()
        if not k:
            return None
        return viz.lots_chart(k["lots"]["lots"])

    @render.plot(alt="Value of each future sensor per tower-year")
    def kaizen_futures():
        k = kaizen()
        if not k:
            return None
        return viz.futures_chart(k["futures"]["slots"], k["futures"]["crew_value_usd_per_tower_year"])

    @render.ui
    def kaizen_transcript():
        return transcript((kaizen() or {}).get("turns", []))

    @render.ui
    def kaizen_dcr():
        k = kaizen()
        if not k:
            return ui.div()
        items = [ui.div(ui.tags.b(f"{i['id']} · {i['area']}"), ui.p(i["change"]),
                        ui.p(i["evidence"], class_="small-note"), ui.p(f"Test: {i['test']}", class_="small-note"),
                        ui.hr()) for i in k["dcr"]["items"]]
        return ui.div(*items)

    # ---------------- grow
    @reactive.effect
    @reactive.event(input.grow_read)
    def _():
        g = crew.grow(input.manual())
        grow.set({"turns": g["turns"], "passport": g["passport"]})

    @reactive.effect
    @reactive.event(input.grow_sign)
    def _():
        g = grow()
        if not g["passport"]:
            return
        s = crew.grow_sign(g["passport"]["asset_id"], "Foreman")
        grow.set({"turns": g["turns"] + s["turns"], "passport": w.passports[g["passport"]["asset_id"]]})

    @render.ui
    def grow_transcript():
        return transcript(grow()["turns"])

    @render.ui
    def grow_passport():
        p = grow()["passport"]
        if not p:
            return ui.p("Pick a manual and let the Onboarder read it.", class_="small-note")
        walls = pd.DataFrame(p["walls"])[["name", "signal", "min", "max", "unit", "condition"]].fillna("")
        sig = ui.div(*[ui.span(("● " if s["fitted"] else "○ ") + s["name"],
                               class_="slot installed" if s["fitted"] else "slot") for s in p["signals"]])
        checks = ui.div(*[ui.p(c["msg"], class_="ok" if c["level"] == "ok" else "err") for c in p["checks"]])
        signed = (ui.p(f"Signed by {p['approved_by']}", class_="approved") if p.get("approved_by")
                  else ui.p("Not signed yet: a human checks the walls first.", class_="small-note"))
        return ui.div(ui.h5(f"{p['asset_id']} · {p['asset_class']}"), checks, signed,
                      ui.HTML(walls.to_html(index=False, classes="opts", border=0)), ui.h6("Signals"), sig)

    @render.ui
    def slot_buttons():
        grow()
        slots_rev()
        tr = w.passports.get("TR-08")
        if not tr:
            return ui.p("Onboard janta_tower_drive_public.md to see the tower's slots.", class_="small-note")
        chips = [ui.span(s["signal"], class_="slot installed" if s["status"] == "installed" else "slot")
                 for s in tr["slots"]]
        return ui.div(*chips, ui.div(ui.input_action_button("install_ae", "Install the acoustic-emission slot",
                                                            class_="btn-outline-success"),
                                     ui.input_action_button("install_grease", "Install the grease sensor slot",
                                                            class_="btn-outline-success"), class_="step-btns"))

    @reactive.effect
    @reactive.event(input.install_ae)
    def _():
        if "TR-08" not in w.passports:
            return
        w.install_slot("TR-08", "acoustic")
        slots_rev.set(slots_rev() + 1)
        g = grow()
        grow.set({"turns": g["turns"] + [{"agent": "Onboarder", "stage": "Grow", "tools": w.trace[-1:],
                                          "say": "Acoustic-emission slot installed on the TR-08 passport: the bearing "
                                                 "detector is live fleet-wide. Check Tower 42."}],
                  "passport": g["passport"]})

    @reactive.effect
    @reactive.event(input.install_grease)
    def _():
        if "TR-08" not in w.passports:
            return
        w.install_slot("TR-08", "grease")
        slots_rev.set(slots_rev() + 1)
        g = grow()
        grow.set({"turns": g["turns"] + [{"agent": "Onboarder", "stage": "Grow", "tools": w.trace[-1:],
                                          "say": "Grease-condition slot installed: water and iron detectors are live. "
                                                 "Tower 19's seal leak now shows weeks earlier."}],
                  "passport": g["passport"]})


app = App(app_ui, server, static_assets=ROOT / "app" / "www")
