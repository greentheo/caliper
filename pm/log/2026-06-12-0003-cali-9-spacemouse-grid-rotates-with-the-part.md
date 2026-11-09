### 2026-06-12 · CALI-9 · SpaceMouse: grid rotates with the part
- Feedback (real-use): with the SpaceMouse, the part rotated/panned/zoomed but the ground grid didn't
  rotate (it panned/zoomed fine). Cause: rotation spun the model *group* while the grid was parented to
  the world; pan/zoom move the camera so the grid followed those but not rotation.
- Fix: parent the GridHelper to `modelGroup` so rotation carries the plane with the part — pan/zoom
  (camera) and rotation (group) are now visually consistent. Verified render (no regression); rotation
  feel pending Theo's confirmation on hardware. 71 passed.
- Commit: cae162f
