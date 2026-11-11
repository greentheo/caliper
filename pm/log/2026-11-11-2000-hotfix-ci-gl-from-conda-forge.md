### 2026-11-11 · Hotfix · CI gets its GL libraries from conda-forge, not apt

Every run on every PR, and on main, died in its first step: `apt-get update` couldn't resolve the Ubuntu mirrors on GitHub's runners ("Temporary failure resolving 'azure.archive.ubuntu.com'", about 30 times a run, three runs on #235). That step only fetched the GL libraries OCCT and VTK load on a headless runner.

They now come from conda-forge with CadQuery, in the same micromamba env (`libgl`, `libegl`, `libglu`). A step after it checks that CadQuery, OCP and VTK's OpenGL module import and that `ldd` finds every library under them. Only if one is still missing does it try apt, three times, each call under a 5-minute timeout with apt's own retries, and it fails the run if the libraries are still missing after that. The run on this PR is the proof.
