"""CALI-127 (#154) — one file per log entry, so PRs stop conflicting on the shared logs."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HEADING = re.compile(r"^#+ *\d{4}-\d{2}-\d{2}", re.M)                 # any dated heading, however it's written
ENTRY = re.compile(r"^### \d{4}-\d{2}-\d{2} \S")
NAME = re.compile(r"^(\d{4}-\d{2}-\d{2})-([01]\d|2[0-3])[0-5]\d(-cali-\d+)?-[a-z0-9-]+\.md$")


@pytest.mark.parametrize("shared", ["pm/LOG.md", "pm/DEMO.md"])
def test_the_shared_files_hold_no_entries(shared):
    found = HEADING.findall((ROOT / shared).read_text(encoding="utf-8"))
    assert not found, f"{shared} has a dated entry: add a file to pm/log/ or pm/demo/ instead (see pm/LOG.md)"


@pytest.mark.parametrize("folder", ["pm/log", "pm/demo"])
def test_every_entry_is_one_file_named_for_its_date(folder):
    entries = sorted((ROOT / folder).iterdir())
    assert entries
    for f in entries:                                                  # make log only reads top-level .md files
        assert f.is_file() and f.suffix == ".md", f"{f.name}: an entry is a .md file directly in {folder}"
        m = NAME.match(f.name)
        assert m, f"{f.name}: name it YYYY-MM-DD-HHMM-cali-N-short-title.md"
        text = f.read_text(encoding="utf-8")
        assert ENTRY.match(text), f"{f.name}: start with a heading, ### YYYY-MM-DD then a space"
        assert text.startswith(f"### {m.group(1)} "), f"{f.name}: its heading's date isn't its name's"
        assert len(HEADING.findall(text)) == 1, f"{f.name}: one entry per file"
