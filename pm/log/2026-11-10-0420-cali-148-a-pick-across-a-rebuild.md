### 2026-11-10 · CALI-148 (#196) · A pick doesn't outlive the rebuild it came before

A pick kept through a Rebuild went to the landing check with the new version's number, so the check could read another edge with the same id. A pick now carries the version it was made on. A rebuild drops it, and the bar says "Rebuilt: click it again", because the faces and edges were renumbered and may have moved. Tried on a scratch stool: pick a face, Parameters to 10 columns, Rebuild: the chip goes and the hint says so.
