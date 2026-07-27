# ECHS Mathematics Open

This repository publishes the fully open, account-free edition of the ECHS Mathematics platform:

- interactive course lessons
- course-aligned practice banks
- adaptive practice and mistake recovery
- timed tests
- locally stored progress, mastery and achievements
- a separately audited AP practice archive

No student, teacher, family or administrator account is created. There is no sign-in, registration or institutional role system in this edition. Bookmarks, lesson completion, attempts, reviews and progress remain in the visitor's browser unless the visitor explicitly exports a progress file.

Production open site:

`https://2ed944-cloud.github.io/ECHS-Math-Open/`

## Navigation contract

The public navigation is intentionally limited to:

1. Lessons
2. Practice Hub
3. Practice
4. Tests
5. Review
6. Progress
7. AP Banks

Legacy `teacher.html` and `parent.html` routes are retained only as safe redirects to local Progress so that old bookmarks do not produce broken pages.

## Question publication boundary

Course practice and the audited AP archive remain separate environments. Canonical IDs, source references, provenance, audit history and publication restrictions are preserved internally. Restricted or review-required AP records remain redacted and cannot enter open practice, assessment or progress calculations.

## Validation

```bash
python tools/validate_open_edition.py
node --check js/platform-foundation.js
node --check sw.js
python -m json.tool manifest.json > /dev/null
```

The `Open Edition QA` workflow runs these checks on relevant pull requests and changes to `main`.

## Deployment note

GitHub Pages is a public static host. Do not add school accounts, learner records, class rosters, private reports, authentication secrets or institutional API configuration to this repository.
