### 2026-10-30 · First run: one sentence in, four answers out (CALI-59 #8)
1. Start Caliper with no designs (or **+ New design**): *What do you want to make?* Type a sentence, e.g. "A step
   stool so my 6-year-old can reach the bathroom sink, from 3/4 in plywood. It has to hold me too, 200 lb." →
   **Start**. Its name is what it is ("Step stool"), not the whole sentence.
2. Leave every question blank → **Build it**. The reply ticks off: *writing down what it has to do · building it ·
   checking it holds · drawing the patterns · scoring it* (about 2½ minutes live; the build is most of it). Then
   it says the four answers in a line each, and the cards on the right are full: what it is and its size, "✓ Holds
   Dad… 8.07x", the shopping list and the patterns to print.
3. **Say it simpler** under the reply: plain words, something like "Even if Dad stands on it, it would need to be
   eight times heavier before it broke."
   Ask "How was the 8x worked out?" and you get the numbers and what the model leaves out.
4. **Or open one of ours:** *Step stool* or *Camper shell* opens a copy with its studies, so every card reads at
   once. `caliper sample list`; `caliper sample save <name> --slug <your design>` makes one from yours.
5. **🎤** beside the box: the browser listens where it can; otherwise it says how to start the Mac's own dictation
   (the 🎤 key, or Fn twice), which types into any box.
6. **Will it work?** ends with what a verdict promises and what it doesn't; so does the build book.
7. When something breaks, **Report it…** (on the red bar, or a failed reply) shows the whole report first:
   what broke, where, the Caliper and macOS versions, nothing of the design. **Open it as a GitHub issue** fills
   in a new issue in your browser for you to submit. Kept on this machine in `~/.caliper/errors.jsonl`.
8. Offline: `python -m pytest tests/test_firstrun.py tests/test_samples.py tests/test_errors.py`.
