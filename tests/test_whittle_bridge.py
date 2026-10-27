"""CALI-38 — the whittle bridge.

A fake whittle server (the four endpoints Caliper uses, speaking whittle's JSON) runs in-process, so
these tests never touch a real whittle. The geometry tests build real parts and are OCCT-gated.
"""

import io
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from caliper import chat, whittle_bridge as wb
from caliper.design import DesignStore

BOX = ("def build(params):\n"
       "    import cadquery as cq\n"
       "    return cq.Workplane('XY').box({dx}, {dy}, {dz}).translate(({x}, 0, {z}))\n")


def _box(dx=1000, dy=1800, dz=1000, x=-1000, z=900):
    return BOX.format(dx=dx, dy=dy, dz=dz, x=x, z=z)


class FakeWhittle:
    """Just enough of whittle's API, recording what Caliper sent."""

    def __init__(self, fail_job=False, stations=3, inflate=0.0):
        self.uploads, self.jobs, self.fail_job, self.n = [], [], fail_job, stations
        self.inflate = inflate      # mm per side — real whittle stations are voxel remeshes, ~½ voxel big
        fake = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _json(self, obj, code=200):
                body = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path == "/api/info":
                    return self._json({"materials": {"xps": {}, "pla": {}}})
                parts = self.path.split("?")[0].strip("/").split("/")
                if parts[:2] == ["api", "jobs"] and len(parts) == 3:
                    return self._json(fake._status(parts[2]))
                if parts[:2] == ["api", "jobs"] and parts[3:4] == ["stations"]:
                    body = fake._station_bytes()     # the uploaded mesh, optionally inflated
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                self._json({"error": "not found"}, 404)

            def do_POST(self):
                n = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(n)
                if self.path.startswith("/api/parts"):
                    fake.uploads.append(body)
                    return self._json({"id": "p1", "closed": True})
                if self.path == "/api/jobs":
                    setup = json.loads(body)
                    if setup.get("kind") not in ("flow", "dual"):
                        return self._json({"error": "kind must be 'load', 'flow' or 'dual'"}, 400)
                    fake.jobs.append(setup)
                    return self._json({"id": "j1", "state": "queued"})
                self._json({"error": "not found"}, 404)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self._polls = 0
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def _station_bytes(self):
        if not self.inflate:
            return self.uploads[-1]
        import trimesh

        mesh = trimesh.load(io.BytesIO(self.uploads[-1]), file_type="stl")
        bodies = []
        for b in mesh.split(only_watertight=False):
            ext = b.bounds[1] - b.bounds[0]
            centre = (b.bounds[0] + b.bounds[1]) / 2
            b.apply_translation(-centre)
            b.apply_scale(1.0)
            b.vertices *= (ext + 2 * self.inflate) / ext
            b.apply_translation(centre)
            bodies.append(b)
        out = io.BytesIO()
        trimesh.util.concatenate(bodies).export(out, file_type="stl")
        return out.getvalue()

    def _status(self, job_id):
        self._polls += 1
        if self._polls < 2:
            return {"id": job_id, "state": "running", "progress": 0.5}
        if self.fail_job:
            return {"id": job_id, "state": "error", "error": "the part voxelized to nothing"}
        return {"id": job_id, "state": "done", "progress": 1.0, "result": {
            "columns": [{"key": "drag", "label": "drag", "format": "{:.0%}"},
                        {"key": "force_n", "label": "N", "format": "{:.1f}"}],
            "stations": [{"removed": 0.05 * i,
                          "metrics": {"drag": 1 - 0.2 * i, "force_n": 300.0 - 40 * i}}
                         for i in range(self.n)]}}

    def close(self):
        self.server.shutdown()


@pytest.fixture
def fake():
    f = FakeWhittle()
    yield f
    f.close()


@pytest.fixture
def hitch(tmp_path):
    """A car block (x 0..1500) and a cargo box behind it (x -1500..-500), car driving +x."""
    s = DesignStore.create("a hitch cargo box", base=str(tmp_path / "designs"))
    s.write_part("car", _box(dx=1500, dy=1790, dz=1300, x=750, z=750), intent="the car's rear")
    s.write_part("box", _box(), intent="the cargo box")
    return s


# --- health, without ever raising -----------------------------------------
def test_health_reports_a_running_whittle(fake):
    h = wb.health(fake.url)
    assert h["ok"] and "xps" in h["materials"]


def test_health_says_why_when_whittle_is_down():
    h = wb.health("http://127.0.0.1:9")
    assert not h["ok"] and "is it running?" in h["error"]


# --- tail-only carving: the part rides behind something ------------------
def test_the_tail_is_the_downstream_end_of_the_part():
    box = ([-1500, -900, 400], [-500, 900, 1400])
    lo, hi = wb.tail_region(box, (-1, 0, 0), fraction=0.4, pad=0)
    assert (lo[0], hi[0]) == (-1500, -1100)        # air moving -x leaves at the low-x end
    assert (lo[1], hi[1], lo[2], hi[2]) == (-900, 900, 400, 1400)


def test_the_tail_follows_the_flow_direction():
    lo, hi = wb.tail_region(([0, 0, 0], [1000, 10, 10]), (1, 0, 0), fraction=0.25, pad=0)
    assert (lo[0], hi[0]) == (750, 1000)


def test_the_tail_needs_an_axis_aligned_flow():
    with pytest.raises(ValueError):
        wb.tail_region(([0, 0, 0], [1, 1, 1]), (-1, 1, 0))


# --- planning the study ----------------------------------------------------
def test_a_free_air_plan_carries_caliper_defaults(hitch):
    pytest.importorskip("cadquery")
    p = wb.plan(hitch, "box", remove_up_to=0.2)
    s = p["setup"]
    assert (s["kind"], s["flow"], s["mirror"], s["flat"]) == ("flow", [-1, 0, 0], "y", ["-z"])
    assert s["removeUpTo"] == 0.2 and s["keepBoxes"] == [] and s["surfaces"] == []
    assert any("Free air" in n for n in p["notes"])
    assert any("voxel grid" in n for n in p["notes"])       # says stations can come back bigger


def test_a_tail_plan_lets_whittle_reshape_only_the_tail(hitch):
    pytest.importorskip("cadquery")
    p = wb.plan(hitch, "box", carve="tail")
    (region,) = p["setup"]["surfaces"]
    lo, hi = region["box"]
    assert hi[0] == pytest.approx(-1500 + 0.4 * 1000)          # the rear 40% of the box
    assert any("savings column" in n for n in p["notes"])     # the totals include the front


def test_an_unknown_carve_is_refused(hitch):
    pytest.importorskip("cadquery")
    with pytest.raises(ValueError, match="carve"):
        wb.plan(hitch, "box", carve="sideways")


def test_a_keep_inset_protects_the_interior(hitch):
    pytest.importorskip("cadquery")
    p = wb.plan(hitch, "box", keep_inset_mm=50)
    lo, hi = p["setup"]["keepBoxes"][-1]
    assert lo[0] == pytest.approx(-1450) and hi[0] == pytest.approx(-550)


def test_an_inset_that_leaves_nothing_is_refused(hitch):
    pytest.importorskip("cadquery")
    with pytest.raises(ValueError, match="no interior"):
        wb.plan(hitch, "box", keep_inset_mm=600)


def test_a_dual_plan_holds_the_part_from_underneath(hitch):
    pytest.importorskip("cadquery")
    p = wb.plan(hitch, "box", kind="dual", keep_inset_mm=50, cargo_kg=40, carve="tail")
    s = p["setup"]
    assert s["kind"] == "dual" and s["material"] == "xps" and s["surfaces"]
    (lo, hi), = [sp["box"] for sp in s["supports"]]
    assert lo[2] < 400 < hi[2] < 500                          # a band along the bottom face
    assert s["cargo"][0]["kg"] == 40


# --- a whole run against the fake ------------------------------------------
def test_a_run_files_every_station_with_the_design(hitch, fake):
    pytest.importorskip("cadquery")
    seen = []
    rec = wb.run(hitch, "box", base=fake.url, poll=0.01, emit=lambda k, t="", **d: seen.append(k))
    assert len(rec["stations"]) == 3
    assert all(open(wb.station_path(hitch, rec["id"], i), "rb").read() for i in range(3))
    assert wb.load_run(hitch, rec["id"])["part"] == "box"
    assert "progress" in seen and seen[-1] == "done"
    assert hitch.history("box")[-1]["action"] == "studied"


def test_a_run_reports_force_saved_in_units_people_decide_with(hitch, fake):
    pytest.importorskip("cadquery")
    rec = wb.run(hitch, "box", base=fake.url, poll=0.01)
    last = rec["stations"][-1]["derived"]
    assert last["saved_n"] == pytest.approx(80.0)
    assert last["saved_kwh_per_100mi"] == pytest.approx(80.0 * wb.KWH_PER_N_PER_100MI, abs=1e-3)
    assert rec["stations"][0]["derived"]["saved_n"] == 0


def test_removal_is_measured_against_the_part_not_taken_from_whittle(hitch, fake):
    pytest.importorskip("cadquery")
    rec = wb.run(hitch, "box", base=fake.url, poll=0.01)
    st = rec["stations"][2]
    assert st["removed"] == pytest.approx(0.10)          # what (fake) whittle claimed
    assert st["removed_part"] == pytest.approx(0.0, abs=1e-3)   # what the station actually is
    assert st["volume_ratio"] == pytest.approx(1.0, abs=1e-3)


def test_a_failed_study_is_named_with_whittles_reason(hitch):
    pytest.importorskip("cadquery")
    bad = FakeWhittle(fail_job=True)
    try:
        with pytest.raises(wb.WhittleError, match="voxelized to nothing"):
            wb.run(hitch, "box", base=bad.url, poll=0.01)
    finally:
        bad.close()


def test_whittle_being_down_is_named_not_a_stack_trace(hitch):
    pytest.importorskip("cadquery")
    with pytest.raises(wb.WhittleError, match="is it running"):
        wb.run(hitch, "box", base="http://127.0.0.1:9", poll=0.01)


# --- bringing a station back ----------------------------------------------
def test_adopting_a_station_makes_it_the_parts_current_revision(hitch, fake):
    pytest.importorskip("cadquery")
    rec = wb.run(hitch, "box", base=fake.url, poll=0.01)
    got = wb.adopt(hitch, rec["id"], 2)
    entry = hitch.design.part("box")
    assert got["version"] == entry.version and entry.origin == "whittled"
    assert got["grew_mm"] == {}                                # exact stations don't grow
    last = hitch.history("box")[-1]
    assert (last["whittle_run"], last["station"]) == (rec["id"], 2)
    assert last["derived"]["saved_n"] == pytest.approx(80.0)


def test_rolling_back_after_adopting_returns_the_parametric_box(hitch, fake):
    pytest.importorskip("cadquery")
    rec = wb.run(hitch, "box", base=fake.url, poll=0.01)
    wb.adopt(hitch, rec["id"], 2)
    res = chat.turn(hitch, "roll it back", scope="box", use_llm=False)
    assert res.action == "revert" and hitch.is_scripted("box")


def test_run_ids_cannot_escape_the_design(hitch):
    assert wb.load_run(hitch, "../../etc") is None
    with pytest.raises(ValueError):
        wb.station_path(hitch, "../x", 0)


# --- what real whittle does: stations are voxel remeshes, ~half a voxel bigger ------------
@pytest.fixture
def inflating():
    f = FakeWhittle(inflate=24.0)
    yield f
    f.close()


def test_an_inflated_station_zero_is_measured_as_bigger_than_the_part(hitch, inflating):
    """Seen live: whittle's '0% removed' station was 8% bigger than the box that was sent."""
    pytest.importorskip("cadquery")
    rec = wb.run(hitch, "box", base=inflating.url, poll=0.01)
    assert rec["stations"][0]["removed_part"] < 0
    assert rec["stations"][0]["volume_ratio"] > 1.0


def test_bringing_back_an_inflated_station_reports_how_far_it_grew(hitch, inflating):
    """A box on a frame that silently drops 24 mm would hit the frame — so it's measured."""
    pytest.importorskip("cadquery")
    rec = wb.run(hitch, "box", base=inflating.url, poll=0.01)
    got = wb.adopt(hitch, rec["id"], 0)
    assert got["grew_mm"]["-z"] == pytest.approx(24.0, abs=0.5)
    assert set(got["grew_mm"]) == {"-x", "+x", "-y", "+y", "-z", "+z"}
    assert hitch.history("box")[-1]["grew_mm"] == got["grew_mm"]


def test_growth_ignores_sub_millimetre_noise():
    assert wb.growth(([0, 0, 0], [10, 10, 10]), ([-0.5, 0, 0], [10.4, 10, 10])) == {}
    assert wb.growth(([0, 0, 0], [10, 10, 10]), ([0, 0, -3], [10, 10, 10])) == {"-z": 3.0}
