"""The order runs are listed in (CALI-97, #100 item 8).

A run's id is the second it started and four random hex digits, so two runs in one second sorted by id came back in
either order, and "the latest" could be the older one. Every listing orders by when the record says it was made, the
id breaking a tie."""

from typing import Iterable


def made(rec: dict) -> float:
    """When a run was made: its record's ``created``, or 0 for one that doesn't say."""
    try:
        return float(rec.get("created") or 0)
    except (TypeError, ValueError):
        return 0.0


def newest_first(records: Iterable[dict]) -> list[dict]:
    """Runs, the one made last first."""
    return sorted(records, key=lambda r: (made(r), str(r.get("id") or "")), reverse=True)
