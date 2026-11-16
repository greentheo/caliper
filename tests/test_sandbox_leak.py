"""CALI-191 (#304): every sandboxed build left its ``caliper_sandbox_*`` folder behind (171,673 on Theo's machine, found in
#303's review). A run now removes its own folder however it ends; a caller's own ``workdir`` is kept; a failed run's is
kept only when asked (``CALIPER_KEEP_SANDBOX=1``); and the server sweeps old ones once at start."""

import os
import tempfile
import threading
import time

import pytest

from caliper import sandbox

pytest.importorskip("cadquery")

BOX = "def build(params):\n    import cadquery as cq\n    return cq.Workplane().box(10, 10, 10)\n"
RAISES = "def build(params):\n    raise ValueError('no box today')\n"
HANGS = "def build(params):\n    import time\n    time.sleep(60)\n"


@pytest.fixture
def tmpdir_(tmp_path, monkeypatch):
    """Temp folders made here, not in the machine's own temp dir."""
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    monkeypatch.delenv(sandbox.KEEP_ENV, raising=False)
    return tmp_path


def _left(root):
    return sorted(n for n in os.listdir(root) if n.startswith(sandbox.PREFIX))


def test_a_build_leaves_no_folder_behind_when_it_succeeds(tmpdir_):
    run = sandbox.run_script(BOX, timeout=120)
    assert run.ok and run.geometry is not None
    assert _left(tmpdir_) == []
    assert run.step_path is None                       # its STEP was read in, and went with its folder


def test_a_build_leaves_no_folder_behind_when_it_fails(tmpdir_):
    run = sandbox.run_script(RAISES, timeout=120)
    assert not run.ok and "no box today" in run.feedback
    assert _left(tmpdir_) == []


def test_a_build_leaves_no_folder_behind_when_it_times_out(tmpdir_):
    t = time.monotonic()
    run = sandbox.run_script(HANGS, timeout=3)
    assert not run.ok and "timed out" in run.error and time.monotonic() - t < 30      # the child was killed
    assert _left(tmpdir_) == []


def test_a_failed_build_s_folder_is_kept_only_when_asked(tmpdir_, monkeypatch, caplog):
    monkeypatch.setenv(sandbox.KEEP_ENV, "1")
    with caplog.at_level("INFO", logger="caliper.sandbox"):
        run = sandbox.run_script(RAISES, timeout=120)
    (kept,) = _left(tmpdir_)
    assert not run.ok and os.path.isfile(os.path.join(tmpdir_, kept, "in.json"))
    assert any(kept in r.getMessage() for r in caplog.records)                     # where to look, said
    ok = sandbox.run_script(BOX, timeout=120)                                      # a good one goes even so
    assert ok.ok and _left(tmpdir_) == [kept]


def test_a_failed_build_s_log_says_where_its_error_went(tmpdir_, caplog):
    with caplog.at_level("INFO", logger="caliper.sandbox"):
        sandbox.run_script(RAISES, timeout=120)
    said = " ".join(r.getMessage() for r in caplog.records)
    assert "no box today" in said and sandbox.KEEP_ENV in said, said


def test_a_caller_s_own_workdir_is_kept(tmpdir_):
    mine = tmpdir_ / "mine"
    mine.mkdir()
    run = sandbox.run_script(BOX, timeout=120, workdir=str(mine))
    assert run.ok and run.step_path == str(mine / "part.step") and os.path.isfile(run.step_path)
    bad = sandbox.run_script(RAISES, timeout=120, workdir=str(mine))
    assert not bad.ok and os.path.isfile(mine / "in.json")


def _aged(path, days):
    t = time.time() - days * 86400
    for root, dirs, files in os.walk(path):
        for f in files:
            os.utime(os.path.join(root, f), (t, t))
    os.utime(path, (t, t))


def test_the_start_sweep_removes_old_folders_and_keeps_fresh_ones(tmp_path):
    old, fresh, busy, other = (tmp_path / n for n in (sandbox.PREFIX + "old", sandbox.PREFIX + "fresh",
                                                      sandbox.PREFIX + "busy", "caliper-preview-old"))
    for d in (old, fresh, busy, other):
        d.mkdir()
        (d / "in.json").write_text("{}")
    for d in (old, busy, other):
        _aged(d, 2)
    sandbox._ACTIVE.add(str(busy))                         # a run in this process uses it
    try:
        assert sandbox.sweep(str(tmp_path)) == 1
    finally:
        sandbox._ACTIVE.discard(str(busy))
    assert not old.exists() and fresh.exists() and busy.exists() and other.exists()


def test_a_folder_with_a_fresh_file_in_it_is_in_use(tmp_path):
    d = tmp_path / (sandbox.PREFIX + "writing")
    d.mkdir()
    (d / "in.json").write_text("{}")
    _aged(d, 2)
    (d / "status.json").write_text("{}")                   # just written: a run of another process is in it
    t = time.time() - 2 * 86400
    os.utime(d, (t, t))                                    # a file written in place leaves the folder's own time
    assert sandbox.sweep(str(tmp_path)) == 0 and d.exists()


def test_the_server_sweeps_once_at_start_and_the_app_alone_never_does(monkeypatch):
    from caliper import server

    swept = threading.Event()
    monkeypatch.setattr(sandbox, "sweep", lambda root=None, **kw: swept.set() or 0)
    import uvicorn

    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: None)
    server.create_app()
    assert not swept.wait(0.5)                             # a test's app touches no temp dir
    server.serve()
    assert swept.wait(10)
