"""CALI-127 (#154) — one file per log entry, so PRs stop conflicting on the shared logs."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DATED = re.compile(r"^### \d{4}-\d{2}-\d{2} ", re.M)
NAME = re.compile(r"^(\d{4}-\d{2}-\d{2})-\d{4}(-cali-\d+)?-[a-z0-9-]+\.md$")


@pytest.mark.parametrize("shared", ["pm/LOG.md", "pm/DEMO.md"])
def test_the_shared_files_hold_no_entries(shared):
    found = DATED.findall((ROOT / shared).read_text(encoding="utf-8"))
    assert not found, f"{shared} has a dated entry: add a file to pm/log/ or pm/demo/ instead (see pm/LOG.md)"


@pytest.mark.parametrize("folder", ["pm/log", "pm/demo"])
def test_every_entry_is_one_file_named_for_its_date(folder):
    files = sorted((ROOT / folder).glob("*.md"))
    assert files
    for f in files:
        m = NAME.match(f.name)
        assert m, f"{f.name}: name it YYYY-MM-DD-HHMM-cali-N-short-title.md"
        text = f.read_text(encoding="utf-8")
        assert text.startswith(f"### {m.group(1)} "), f"{f.name}: its heading's date isn't its name's"
        assert len(DATED.findall(text)) == 1, f"{f.name}: one entry per file"
