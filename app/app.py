"""PitCrew operator console (Shiny for Python).

    shiny run app/app.py --port 8000          # then open the port (VS Code web: the Ports tab)

Run -> Improve -> Grow, with the approval card between the crew and the machine.
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
from pitcrew.passport import manuals  # noqa: E402
from pitcrew.tower import Fleet  # noqa: E402
from pitcrew.world import World  # noqa: E402

SHARED_FLEET = Fleet().run()  # deterministic; shared read-only by every session
MILL_ROWS = mill.creep_scenario()
MODE = os.environ.get("PITCREW_LLM", "offline")
MODE_LABEL = {"offline": "Crew: offline (deterministic narration)", "bedrock":
              f"Crew: Bedrock · {os.environ.get('PITCREW_MODEL_ID', 'default model')}",
              "scripted": "Crew: Strands + scripted model"}.get(MODE, MODE)


def new_world() -> World:
    w = World()
    w.__dict__["fleet"] = SHARED_FLEET
    return w


# ------------------------------------------------------------------ small UI helpers
def md_inline(text: str) -> str:
    t = html.escape(text or "")
    parts = t.split("**")
    return "".join(f"<b>{p}</b>" if i % 2 else p for i, p in enumerate(parts))


def transcript(turns: list[dict]):
    if not turns:
        return ui.p("The crew is idle.", class_="small-note")
    out = []
    for t in turns:
        chips = []
        for x in t.get("tools", []):
            args = ", ".join(f"{k}={v}" for k, v in (x.get("args") or {}).items() if k not in ("evidence", "parts"))
            body = json.dumps(x.get("result"), indent=1, default=str)
            chips.append(ui.tags.details(ui.tags.summary(ui.span(f"{x['tool']}({args})", class_="chip")),
                                         ui.tags.pre(body[:4000]), class_="tool"))
        out.append(ui.div(ui.div(ui.span(t["agent"], class_="who"), ui.span(t.get("stage", ""), class_="stage")),
                          ui.div(ui.HTML(md_inline(t["say"])), class_="say"), *chips,
                          class_=f"turn {t.get('stage', '')}"))
    return ui.div(*out)


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


# ------------------------------------------------------------------ layout
def run_mill_panel():
    return ui.nav_panel(
        "Run · Mill",
        ui.layout_columns(
            ui.div(
                ui.card(ui.card_header("VM-07 live signals (AI4I walls)"), ui.output_plot("mill_signals", height="300px")),
                ui.card(ui.card_header("Safe operating envelope"), ui.output_plot("mill_envelope", height="360px")),
            ),
            ui.div(
                ui.card(ui.card_header("Demo"),
                        ui.p("Start with a normal window, then change the sensor story.", class_="lead"),
                        ui.div(ui.input_action_button("mill_change", "1 · Harder steel lot arrives", class_="btn-warning"),
                               ui.input_action_button("mill_assess", "2 · Crew: assess and plan", class_="btn-primary"),
                               ui.input_action_button("mill_reset", "Reset", class_="btn-outline-secondary"),
                               class_="step-btns"),
                        ui.output_ui("mill_status")),
                ui.card(ui.card_header("Crew"), ui.output_ui("mill_transcript")),
                ui.output_ui("mill_approval"),
            ),
            col_widths=[7, 5]))


def run_tower_panel():
    return ui.nav_panel(
        "Run · Janta towers",
        ui.layout_columns(
            ui.div(
                ui.card(ui.card_header("Fleet: 48 TR-08 towers, three DFW sites (simulated drive model)"),
                        ui.output_plot("fleet_map", height="300px")),
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
                        ui.p("Park & Price: keep tracking, coast, park at the best azimuth or send a technician "
                             "tomorrow - each priced with the Shadow Calculator energy model and a weather "
                             "Monte Carlo of the drive.", class_="small-note")),
                ui.card(ui.card_header("Crew"), ui.output_ui("tower_transcript")),
                ui.output_ui("tower_approval"),
            ),
            col_widths=[7, 5]))


def improve_panel():
    return ui.nav_panel(
        "Improve",
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
                ui.card(ui.card_header("Crew"), ui.output_ui("kaizen_transcript")),
                ui.card(ui.card_header("Design-change request for TR-09 (draft)"), ui.output_ui("kaizen_dcr")),
            ),
            col_widths=[7, 5]))


def grow_panel():
    return ui.nav_panel(
        "Grow",
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
                ui.card(ui.card_header("Crew"), ui.output_ui("grow_transcript")),
                ui.card(ui.card_header("Future hardware slots"),
                        ui.p("Signals the manual lists as not fitted become slots: the agents that need them already "
                             "exist and switch on the day the sensor is installed. Try it on the Janta tower: "
                             "install the acoustic-emission slot, then look at Tower 42 on the Towers tab.",
                             class_="small-note"),
                        ui.output_ui("slot_buttons")),
            ),
            col_widths=[7, 5]))


def story_panel():
    pr = (ROOT / "docs" / "PRFAQ.md").read_text()
    return ui.nav_panel("Why (press release)", ui.card(ui.markdown(pr)))


def arch_panel():
    svg = (ROOT / "docs" / "architecture.svg").read_text()
    table = pd.DataFrame([
        ("Agents", "Strands Agents SDK, Graph for Run (fixed order, repeatable), single agents for Improve/Grow"),
        ("Runtime", "Amazon Bedrock AgentCore Runtime (agentcore/agent.py)"),
        ("Tools", "AgentCore Gateway exposing the World tools as MCP; CMMS via OpenAPI (MaintainX pattern)"),
        ("Guardrails", "AgentCore Policy (Cedar): POs over $500 and every setpoint change need the foreman"),
        ("Knowledge", "Bedrock Knowledge Base over manuals; AgentCore Memory for incidents; passports in S3"),
        ("Suppliers", "A2A: supplier agents on their own runtimes (agentcore/supplier_a2a.py)"),
        ("Energy", "Table exported from the Janta Shadow Calculator field model (scripts/export_energy_table.py)"),
        ("Data", "AI4I 2020 (UCI 601); tower drive model anchored to DuraMAT tracker motor current, NASA IMS"),
    ], columns=["Piece", "On AWS"])
    return ui.nav_panel("Architecture", ui.card(ui.HTML(svg)),
                        ui.card(ui.HTML(table.to_html(index=False, classes="opts", border=0))))


app_ui = ui.page_navbar(
    run_mill_panel(), run_tower_panel(), improve_panel(), grow_panel(), story_panel(), arch_panel(),
    ui.nav_spacer(), ui.nav_control(ui.span(MODE_LABEL, class_="mode-badge")),
    title=ui.span("PitCrew", ui.span(f"Run · Improve · Grow  v{__version__}", class_="brand-sub")),
    header=ui.include_css(ROOT / "app" / "www" / "styles.css"),
    window_title="PitCrew",
)


# ------------------------------------------------------------------ server
def server(input, output, session):
    w = new_world()
    crew = Crew(w, MODE)
    mill_step = reactive.value(0)  # 0 normal, 1 changed, 2 planned, 3 approved
    mill_plan = reactive.value(None)
    mill_exec = reactive.value(None)
    tower_plan = reactive.value(None)
    tower_exec = reactive.value(None)
    kaizen = reactive.value(None)
    grow = reactive.value({"turns": [], "passport": None})
    slots_rev = reactive.value(0)  # bumps when a future hardware slot is installed

    # ---------------- mill
    @reactive.effect
    @reactive.event(input.mill_reset)
    def _():
        nonlocal w, crew
        w = new_world()
        crew = Crew(w, MODE)
        mill_step.set(0)
        mill_plan.set(None)
        mill_exec.set(None)

    @reactive.effect
    @reactive.event(input.mill_change)
    def _():
        mill_step.set(max(mill_step(), 1))

    @reactive.effect
    @reactive.event(input.mill_assess)
    def _():
        if mill_step() < 1:
            mill_step.set(1)
        with ui.Progress() as p:
            p.set(message="Crew is assessing VM-07...")
            mill_plan.set(crew.plan_mill())
        mill_step.set(2)

    @reactive.effect
    @reactive.event(input.mill_approve)
    def _():
        if mill_plan() is None:
            return
        mill_exec.set(crew.execute(mill_plan(), "Foreman"))
        mill_step.set(3)

    @render.plot(alt="VM-07 spindle power and overstrain over parts")
    def mill_signals():
        now = 19 if mill_step() == 0 else 21
        return viz.mill_signals(MILL_ROWS, now)

    @render.plot(alt="Safe operating envelope in speed and torque")
    def mill_envelope():
        st = dict(w.mill_state) if mill_step() < 3 else dict(rpm=1500.0, torque=56.0, wear=120.0, d_temp=8.2,
                                                             creep=0.3, variant="L")
        if mill_step() == 0:
            st.update(torque=40.0, d_temp=10.2)
        lc = None
        if mill_step() >= 2 and mill_plan():
            r = mill_plan()["recommendation"]
            if r["key"] == "lift_and_coast":
                lc = {"rpm": r["rpm"], "torque": r["torque"]}
        return viz.envelope(st, lc)

    @render.ui
    def mill_status():
        s = mill_step()
        msg = ["Normal window: 40 Nm, 6.3 kW, wide margins on every wall.",
               "A harder steel lot arrived: torque jumped to 56 Nm and creeps 0.3 Nm per part.",
               "Plan ready: the foreman decides.", "Approved and executing."][s]
        return ui.p(msg, class_="small-note")

    @render.ui
    def mill_transcript():
        turns = (mill_plan() or {}).get("turns", []) + (mill_exec() or {}).get("turns", [])
        return transcript(turns)

    @render.ui
    def mill_approval():
        p = mill_plan()
        if not p:
            return ui.div()
        rec = p["recommendation"]
        body = [options_table(p["options"], rec["key"], "mill"),
                ui.p(f"Assumptions: ${p['assumptions']['contribution_per_hour']:,.0f}/h lost margin, "
                     f"{p['assumptions']['cycle_min']:.0f} min per part, planned tool change "
                     f"{p['assumptions']['planned_tool_change_min']:.0f} min. Replace with the plant's numbers.",
                     class_="small-note")]
        if mill_exec():
            wo = mill_exec().get("work_order") or {}
            body.append(ui.p(f"Approved by the foreman · {wo.get('wo', '')} scheduled · setpoint now "
                             f"{w.mill_state['setpoint']}", class_="approved"))
        else:
            body.append(ui.input_action_button("mill_approve", f"Approve: {rec['title']}", class_="btn-success"))
        return ui.card(ui.card_header("Approval: the foreman decides"), *body, class_="approval")

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
            body.append(ui.input_action_button("tower_approve", f"Approve: {rec['title']}", class_="btn-success"))
        return ui.card(ui.card_header(f"Approval: tower {p['tower_id']}"), *body, class_="approval")

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
