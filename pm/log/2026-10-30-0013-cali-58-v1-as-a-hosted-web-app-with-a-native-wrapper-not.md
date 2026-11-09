### 2026-10-30 · Decision · V1 as a hosted web app with a native wrapper, not the App Store (CALI-58, #7)
- **Theo:** "for app store, I'm thinking that no it's probably not going to work, and honestly, trying to make it work
  is going to add a lot of complexity. What we might be better off doing is creating this as a web app and service
  (Railway?) and then doing a wrapper around it. Obviously needs to be more than just a wrapper to a webservice, so
  we can add a few distinguishing features, but ultimately no code will need to be run on the user side. This of
  course, is going to present a compute bandwidth problem since FEA can be compute intense. perhaps that would be
  something we can keep local... dunno"
- What it changes: generated code runs on the server, so the real sandbox (CALI-66, #26) becomes multi-tenant
  isolation; accounts, storage and the API key move server-side; error reports (CALI-59) can go to the service with
  the person's say-so instead of a GitHub issue. Open: where the FEA runs (a worker pool, or the wrapper's own
  fixed, signed code on the person's machine) and what the wrapper does that the web page can't.
- Not started: needs a spec (`specs/`), then #6 and #7 rewritten to match.
