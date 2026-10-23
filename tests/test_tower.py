import pytest

from pitcrew.decide import diagnose, park_and_price
from pitcrew.ops import Ops
from pitcrew.tower import COUNTS_PER_OUTPUT_DEG, Fleet, project


@pytest.fixture(scope="module")
def fleet():
    return Fleet().run()


def test_encoder_resolution():
    assert round(COUNTS_PER_OUTPUT_DEG, 1) == 241.8


def test_fleet_is_deterministic(fleet):
    again = Fleet().run()
    assert len(again.incidents) == len(fleet.incidents)
    assert again.today().loc[7, "grease"] == pytest.approx(fleet.today().loc[7, "grease"])


def test_lot_b_fails_more(fleet):
    import pandas as pd
    inc = pd.DataFrame(fleet.incidents)
    ty = fleet.log_df.groupby("lot").size() / 365
    rate = inc.groupby("lot").size() / ty
    assert rate["B"] > 3 * rate["A"]


def test_demo_towers_are_flagged_by_the_right_detector(fleet):
    assert diagnose(fleet, 7)["primary"]["detector"] == "friction"
    assert diagnose(fleet, 31)["primary"]["detector"] == "backlash"
    assert diagnose(fleet, 42)["primary"] is None  # invisible to today's sensors
    assert diagnose(fleet, 42, slots=("acoustic",))["primary"]["detector"] == "acoustic"
    assert diagnose(fleet, 19, slots=("grease_water",))["primary"]["detector"] == "grease_water"


def test_parking_removes_stall_risk(fleet):
    track = project(fleet, 7, "track", 6, runs=120)["p_fail_by"](6)
    park = project(fleet, 7, "park", 6, runs=120)["p_fail_by"](6)
    assert track > 0.4 and park == 0.0


def test_park_and_price_recommends_cheapest(fleet):
    r = park_and_price(fleet, 7, Ops(), runs=120)
    best = min(r["options"], key=lambda o: o["expected_cost_usd"])
    assert r["recommendation"]["key"] == best["key"] == "park"
    assert r["visit_in_days"] == 6  # next Thursday route from Fri Oct 23
