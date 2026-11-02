"""CALI-87 (#63, finding 1) — the printed rest of a part, kept between asks, is kept per what-if."""

import pytest

from caliper import construction as C
from caliper.design import DesignStore

from .test_mixed import MIXED

pytest.importorskip("cadquery")


def test_a_what_if_and_the_part_as_drawn_each_get_their_own_printed_rest(tmp_path):
    store = DesignStore.create("a stool", base=str(tmp_path / "designs"))
    store.write_part("stool", MIXED, intent="a plywood top on printed sides")
    C._PRINTED.clear()
    thick = abs(C.printed_solid(store, "stool", C.declared(store, "stool", build={"top": 19.05})).volume)
    plain = abs(C.printed_solid(store, "stool").volume)                  # asked second: the cache had the what-if
    C._PRINTED.clear()
    fresh = abs(C.printed_solid(store, "stool").volume)
    assert plain == pytest.approx(fresh, rel=1e-6)                         # the part as drawn, not the what-if's
    assert thick < plain                                                    # a thicker top leaves less to print
