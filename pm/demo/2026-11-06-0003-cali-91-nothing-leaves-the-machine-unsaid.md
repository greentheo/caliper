### 2026-11-06 · Nothing leaves the machine unsaid (CALI-91 #68)
1. **Press 🎤:** it asks first, "Your browser turns speech into words by sending it to its maker (Google, in Chrome).
   Talk anyway?". **Type instead** doesn't listen. **Talk** does, and the next press doesn't ask again.
2. **With a key set:** under the "What do you want to make?" box, and under the chat box until you send something:
   "What you type goes to Claude (Anthropic's AI) to design it."
3. **With no key:** the box says "Building a new design needs a Claude key (see .env.example). Until then, open one of
   ours below", and a new design's Build it is replaced by that line. No job starts.
4. Offline: `PYTHONPATH=src python -m pytest -rs tests/test_privacy.py`.
