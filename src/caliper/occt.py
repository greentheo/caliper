"""One lock for OCCT in this process.

OCCT (under CadQuery) isn't safe to call from two threads at once. The web server answers on a thread pool
and runs jobs on threads of their own, and two page loads measuring the design together took the process
down (SIGSEGV / SIGABRT). Everything that builds, imports or measures a B-rep in this process goes through
``OCCT``; it's re-entrant, so a measurement that loads its parts takes it once.
"""

import threading

OCCT = threading.RLock()
