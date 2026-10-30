import os

import pytest
import trimesh

from caliper.measure import Geometry

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture
def fixtures_dir() -> str:
    return FIXTURES


@pytest.fixture
def box_geom():
    """A solid box mesh of given extents (mm)."""

    def _make(dx=10.0, dy=20.0, dz=30.0) -> Geometry:
        return Geometry.from_mesh(trimesh.creation.box(extents=(dx, dy, dz)))

    return _make


@pytest.fixture
def two_box_geom() -> Geometry:
    """Two disjoint unit boxes → a single mesh with two bodies."""
    a = trimesh.creation.box(extents=(10, 10, 10))
    b = trimesh.creation.box(extents=(10, 10, 10))
    b.apply_translation([50, 0, 0])
    return Geometry.from_mesh(trimesh.util.concatenate([a, b]))


@pytest.fixture(autouse=True)
def _no_personal_shop(tmp_path_factory, monkeypatch):
    """CALI-48: tests plan the making with a hand-tool shop and the rough print estimate, whatever this
    machine's own ~/.caliper/shop.yaml or slicer says."""
    monkeypatch.setenv("CALIPER_SHOP", str(tmp_path_factory.mktemp("shop") / "shop.yaml"))
    monkeypatch.setenv("CALIPER_SLICER", "")
