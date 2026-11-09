### 2026-11-05 · CALI-96 (#78), #96 rework · "Not trusted yet" everywhere a filled part's strength shows
The foreman's six items. The rule: wherever a strength verdict rests on the filled solid, it never reads holding.
- **The scorecard** grades it "untrusted", so the build package isn't "ready to cut". `d5a66fd`
- **The numbers layer and the 3D view** say "not trusted: a filled-in shape": the panel header, the case badges,
  the heat callout, the lightening line and the step previews. `b3adda5`
- **The cache fails closed:** "couldn't check its shape" is never holding, and isn't kept. `79fe045`
- **The kids' book:** no stand-on-it page; "Don't stand on it yet: a grown-up checks it first". `c349f75`
- **The design card** leads with the verdict, with the check's name after. `85bc844`
- **Studies and Lighten** read the part as it is now, so old runs say so too. `be73bd1`

---
