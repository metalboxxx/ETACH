# ETACH

**English Test Assistant: Curate & Help.** A desktop app for Windows that helps an English tutor work with the
paper tests Vietnamese students bring home from school (grades 6–12).

## What it does

1. The teacher photographs a test, checks the photos, and presses **Run**, then goes back to the student.
2. The app reads the photos and saves the clean test once in a searchable **test bank**. If a student filled it in,
   it also saves the student's answers.
3. It prepares the **key** (the correct answers) for questions that have none.
4. When the teacher asks, it **grades** the student's answers, explains the mistakes, and builds up the student's
   weak points across tests.
5. The teacher glances at the result and prints it.

## Design priorities

- **Little teacher time during a lesson.** About half a minute before Run; nothing while it runs.
- **Honest about doubt.** Anything the app is unsure of is marked `?` for the teacher to check, never shown as a
  confident right or wrong.
- **One clean test bank.** Every test has the same structure however messy the paper was, and is stored once.
- **Private and offline.** Everything runs on the teacher's own computer with local models. Students' work never
  leaves it, and there is nothing to pay per use.
- **Code before models.** Whatever can be done by rules (numbering, points, scoring) is done in code; the models read
  the photos, make the key, grade and explain.
- **Measured, not guessed.** Every change to the models or their prompts is scored on real tests before it is kept.

More: [`docs/PRD.md`](docs/PRD.md) describes the app in full; [`docs/dev-setup.md`](docs/dev-setup.md) is for
developers.
