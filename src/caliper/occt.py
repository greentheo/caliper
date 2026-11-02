"""One lock for OCCT in this process.

OCCT (under CadQuery) isn't safe to call from two threads at once. The web server answers on a thread pool
and runs jobs on threads of their own, and two page loads measuring the design together took the process
down (SIGSEGV / SIGABRT). Everything that builds, imports or measures a B-rep in this process goes through
``OCCT``; it's re-entrant, so a measurement that loads its parts takes it once.

The same goes for manifold3d's booleans (CALI-82: a part with a printed rest is the part less its sheets,
and three requests for its cards, its making and its balance took the process down together): they take
this lock too.
"""

import threading

OCCT = threading.RLock()
