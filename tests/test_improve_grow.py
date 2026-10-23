import pytest

from pitcrew.passport import MANUALS, from_manual, install_slot, manuals, sign


@pytest.mark.parametrize("name", manuals())
def test_every_manual_onboards_cleanly(name):
    p = from_manual(MANUALS / name)
    assert all(c["level"] == "ok" for c in p["checks"]), p["checks"]
    assert p["walls"] and p["slots"]
    signed = sign(p, "tester")
    assert signed["approved_by"] == "tester"


def test_slot_install_unlocks_detectors():
    p = from_manual(MANUALS / "vm07_mill_manual.md")
    first = p["slots"][0]["signal"].split()[0].lower()
    p2 = install_slot(p, first)
    assert any(s["status"] == "installed" for s in p2["slots"])
