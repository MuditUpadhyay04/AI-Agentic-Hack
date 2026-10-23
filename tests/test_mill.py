from pitcrew import mill


def test_walls_match_ai4i_rules():
    m = mill.margins(1500, 56, 120, 8.2, "L")
    assert round(56 * mill.omega(1500)) == 8796
    assert 0 < m["PWF_high"] < 0.03  # 2% under the 9 kW ceiling
    assert m["HDF"] == 1.0  # 1,500 rpm is above 1,380
    assert mill.margins(1370, 40, 50, 8.2)["HDF"] == -1.0
    assert mill.margins(1500, 40, 300, 10)["OSF"] < 0  # 12,000 min*Nm > 11,000 for L


def test_as_is_crosses_power_wall_in_five_parts():
    n, walls = mill.parts_until_wall(1500, 56, 120, 8.2)
    assert (n, walls) == (5, ["PWF_high"])


def test_lift_and_coast_reaches_shift_change_with_margin():
    lc = mill.lift_and_coast(56, 120, 8.2, parts_needed=30)
    assert lc["rpm"] >= 1380 and lc["torque"] < 56
    assert lc["parts_to_wall"] > 30
    assert min(v for k, v in lc["margins_at_window"].items() if k != "TWF") >= 0.08
    assert (lc["rpm"], lc["torque"], lc["parts_to_wall"]) == (1400, 47.0, 36)


def test_lift_and_coast_is_cheapest_with_default_assumptions():
    st = dict(rpm=1500, torque=56, wear=120, d_temp=8.2, creep=0.3, variant="L", parts_to_window=30)
    opts = {o.key: o for o in mill.mill_options(st)}
    assert opts["run_as_is"].p_fail_before_window > 0.95
    assert opts["lift_and_coast"].cost_usd < opts["stop_now"].cost_usd < opts["run_as_is"].cost_usd
