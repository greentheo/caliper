### 2026-06-12 · Recent parts (browse/load) + hole-count hang fix
**New:** a "Recent parts" panel in the webapp — every run is listed (newest first, with its label +
timestamp); click one to load its spec, report, and 3D mesh; refine from there forks a new part.
**Fixed:** an intent like "…for 2020 with two M6 holes" used to hang (it read the extrusion size 2020
as the hole count → drilling 2020 holes). Now parsed correctly + clamped. **Try:**
```bash
make serve   # build a few parts, then click between them in "Recent parts" on the left
```
