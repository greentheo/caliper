### 2026-11-06 · CALI-91 (#68) · Words leave the machine only when the person sends them
- **The 🎤 asks first** (rule 6). A browser's speech recognition sends the audio to its maker. On the first press:
  "Your browser turns speech into words by sending it to its maker (Google, in Chrome). Talk anyway?", with **Talk**
  and **Type instead**. The answer is kept in that browser's `localStorage`, every read and write in try/catch; if
  it's forgotten, it asks again. After Type instead, the next press offers the computer's dictation and a Talk button,
  and never listens unasked.
- **On the device, it doesn't ask:** where `SpeechRecognition.available({processLocally: true})` says "available", it
  listens with `processLocally` and nothing leaves. Checked on this machine: the app's browser pane (Chrome/152) has
  the API and reports on-device "unavailable", so it asks. Chrome and Safari themselves weren't checked.
- **The fallback names no machine it can't see:** "Use your computer's dictation: on a Mac, press the 🎤 key (or Fn
  twice)."
- **What's typed goes to Claude, said:** under the first-run box, and under the chat box until the first message is
  sent, when a key is set.
- **With no key, Build it says what's missing instead of failing:** "Building a new design needs a Claude key (see
  .env.example). Until then, open one of ours below." The API refuses a first build with a 409 in those words, the
  questions' Build it records the answers and starts nothing, and the page shows the line instead of the button.
- Tests: `tests/test_privacy.py` (node: `rec.start()` only after a yes or on the device; Type instead; the second
  press; cleared storage; blocked storage); `test_firstrun` (no key: no job, the 409). `?v=44`.
