"""#17 slice C's page line (#415, the author lane's ask): a plan's build says which group it's building in.

The build emits ``{step: "group", text: "The box: 5 parts"}`` once as each group starts, before its first part.
`followBuild`'s `mark` dropped it, since `BUILD_STEPS` has no "group": reviewer-2 saw only "Building the box floor…".
Now the group is kept beside each of its parts' lines, "The box (5 parts) · Building the box floor…", until the next group
or the next step. A plan without groups emits none, and reads as before."""
from .test_first_build_progress import _bubble

_GO = """followBuild('j'); const on = running[0].on;
on({kind: 'step', step: 'plan', text: 'Planning its parts'});"""


def test_the_group_is_said_beside_each_of_its_parts():
    got = _bubble(_GO + """
      on({kind: 'step', step: 'group', group: 'platform', text: 'The platform: 2 parts'});
      on({kind: 'step', step: 'build', text: 'Building the deck'}); const deck = head(0);
      on({kind: 'step', step: 'build', text: 'Building the joists'}); const joists = head(0);
      on({kind: 'step', step: 'group', group: 'box', text: 'The box: 5 parts'});
      on({kind: 'step', step: 'build', text: 'Building the box floor'}); const floor = head(0);
      on({kind: 'step', step: 'measured', text: 'Measuring it'}); const measured = head(0);
      return {deck, joists, floor, measured};""")
    assert "The platform (2 parts) · Building the deck…" in got["deck"]
    assert "The platform (2 parts) · Building the joists…" in got["joists"]
    assert "The box (5 parts) · Building the box floor…" in got["floor"]              # the next group replaces it
    assert "Measuring it…" in got["measured"] and "box" not in got["measured"]           # and the next step ends it


def test_a_group_s_line_shows_as_soon_as_it_starts():
    got = _bubble(_GO + """on({kind: 'step', step: 'build', text: 'Building it'});
      on({kind: 'step', step: 'group', group: 'box', text: 'The box: 1 part'}); return head(0);""")
    assert "The box (1 part) · Building it…" in got


def test_a_plan_without_groups_reads_as_before():
    got = _bubble(_GO + """on({kind: 'step', step: 'build', text: 'Building the seat'}); return head(0);""")
    assert "Building the seat…" in got and "(" not in got.split("Building")[0].split("</span>")[-1]


def test_a_group_s_words_are_text():
    import re

    from .test_first_build_progress import BUBBLE, JS, _fn, _run

    src = open(JS).read()
    esc = re.search(r"^const esc = .*;$", src, re.M).group(0)
    fns = "".join(_fn(src, n) for n in ("elapsedText", "authoringWords", "buildRanFor", "followBuild"))
    steps = re.search(r"^const BUILD_STEPS = .*?;\n(?=\S)", src, re.M | re.S).group(0)
    bubble = BUBBLE.replace("const esc = (s) => s;", esc)
    got = _run(f"{bubble}\n{steps}\n{fns}\nconst out = await (async () => {{ " + _GO + """
      on({kind: 'step', step: 'group', group: 'x', text: 'The <b>box</b>: 2 parts'});
      on({kind: 'step', step: 'build', text: 'Building it'}); return head(0); })();\nconsole.log(JSON.stringify(out));""")
    assert "The &lt;b&gt;box&lt;/b&gt; (2 parts) · Building it…" in got
