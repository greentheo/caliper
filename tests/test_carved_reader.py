"""CALI-90 (#66 item 3) and CALI-92 (#70 items 8 and 9): one reader of a script's CARVED line, anchored to a line
that starts with it, with or without an annotation, used by carve.strip, carve.carved, assembly._carved and the
design's "carved" flag."""

import pytest

from caliper import assembly, carve

HEAD = 'import cadquery as cq\n\nBUILD = {"t": 19.05}\n\n\ndef build(params):\n    return None\n'


@pytest.mark.parametrize("line, name", [
    ('CARVED = "carved-1.stl"', "carved-1.stl"),
    ("CARVED = 'carved-1.stl'", "carved-1.stl"),
    ('CARVED: str = "carved-1.stl"', "carved-1.stl"),      # annotated
    ('    CARVED = "carved-1.stl"', "carved-1.stl"),       # indented
    ('UNCARVED = "x"', None),                              # another name ending in it
    ('# CARVED = "carved-1.stl" was the old one', None),   # a comment that mentions it
    ('NOT_CARVED = "carved-1.stl"', None),
])
def test_one_reader_finds_only_a_carved_line(line, name):
    script = HEAD + "\n" + line + "\n"
    assert assembly.carved_file(script) == name
    assert carve.carved(script) == (name is not None)


@pytest.mark.parametrize("line", ['UNCARVED = "x"', '# mentions CARVED = "y" in a comment', 'NOT_CARVED = "z"'])
def test_strip_leaves_a_line_that_isnt_the_carve_whole(line):
    script = HEAD + "\n" + line + "\n"
    assert carve.strip(script) == script                   # "UNCARVED = "x"" became "UN"


@pytest.mark.parametrize("line", ['CARVED = "carved-1.stl"', 'CARVED: str = "carved-1.stl"'])
def test_strip_takes_the_carve_and_its_note_off(line):
    script = HEAD + "\n\n# The printed rest as carved by the strength study (CALI-82): …\n" + line + "\n"
    assert carve.strip(script) == HEAD


def test_the_designs_carved_flag_is_the_same_reader(tmp_path):
    from caliper import design_api
    from caliper.design import DesignStore

    store = DesignStore.create("a stool", base=str(tmp_path))
    store.write_part("a", HEAD + '\n# not CARVED yet: say "carve it"\n', intent="x")
    store.write_part("b", HEAD + '\nCARVED: str = "carved-1.stl"\n', intent="x")
    got = {p["id"]: p["carved"] for p in design_api.design_state(store)["parts"]}
    assert got == {"a": False, "b": True}
