# Validator fixtures

These fixtures exercise the repository validators themselves.

They are not active project tasks or QA records. `scripts/test-validators.mjs`
runs the validators against these files and expects:

- files under `valid/` to pass;
- files under `invalid/` to fail.

The front-matter, intent, and QA fixtures run through their validators with
`--fixture` and use `fixture_path` front matter so the validators can apply the
normal type and canonical-path rules while the fixture files remain under
`_evals/`. The general link validator deliberately ignores fixture front-matter
types because intentionally-invalid metadata belongs to the fixture runner.

The QA invalid fixture without `qa_schema` also verifies legacy compatibility:
legacy plans still require an `INV-*`, while schema v2 accepts `None`.
