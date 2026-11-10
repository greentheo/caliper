### 2026-11-10 · CALI-102 (#94, slice b) · Moving parts in the tree

Drag a part above or below another to reorder it, or onto another to sit under it. That's saved with the design, as display only: `part_tree` in `design.yaml`, read by nothing but the tree. No part's id, file, version or check changes, and the design's own list of parts stays in its order. A part's eye hides what sits under it too. Moving a *piece* into another part changes two scripts, so it stays with #3. The mockup Theo approved doesn't draw any of this, so the look follows the tree it did draw. At phone width rows can't be dragged, and the drawer says moving parts needs a wider window. The whole suite is CI's.

From the review: the line for "below" sits below everything under the part, where it will land. A part dropped under a hidden part is hidden too. A drop that has to wait for a job on the design says so. A move doesn't jump the design to the top of the picker.
