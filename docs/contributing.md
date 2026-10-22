<!--
File: docs/contributing.md
Purpose: Define consistent source, configuration and documentation conventions.
Maintainer: sunshine-engineer
Modified: 2026-10-23
-->

# Contributor conventions

## File metadata and ownership

Project-owned text files use their format's comment syntax or a Python module
docstring to state file path, purpose, default maintainer and modified date.
Use `Maintainer: sunshine-engineer` unless a different maintainer is explicitly
provided. This is the requested maintenance default, not a claim of original
authorship or a record of operational handover acceptance. Do not add guessed
names, email addresses, copyright notices or third-party ownership.

Use an ISO date (`YYYY-MM-DD`) for actual edits, not a dynamic import-time date.
The consistency checker validates date syntax, not whether every file was edited
today. Preserve dated evidence within historical reports.

Strict JSON does not support comment headers: retain its schema and record file
metadata in the [inventory](file-inventory.md). Preserve binary PDF/PNG assets,
generated `uv.lock` content and the legal LICENSE text; record the review without
inserting an artificial header. Regenerate lock metadata only through uv when
project dependencies change. New dependencies require a focused justification.

## Python structure and docstrings

Use the module docstring/header, standard-library imports, third-party imports,
local imports, constants, logically ordered helpers/classes, and final entry
point. Keep provider integrations lazy where that preserves provider-free imports
and safe startup. Streamlit execution lives in `main()` rather than module import
side effects. Do not reorder dependent initialization merely to satisfy a template.

Every explicit class and callable, including private/nested helpers and test
fixtures, has a purpose-specific docstring. Use Google-style `Args`, `Returns`,
`Yields`, `Raises` and class `Attributes` sections where applicable. Do not document
`self`/`cls` as caller parameters. Explain lazy streams and persistence failure
semantics; examples should clarify non-obvious contracts, not repeat signatures.
Test methods can have concise scenario descriptions when they take no caller
arguments and return no value. Lambdas are expressions rather than definitions;
their injected callback contracts are documented at the service boundary.

Black enforces 88-column Python formatting, Ruff enforces import organization,
basic errors and missing public docstrings, and the consistency script also
checks private/nested definitions and documented parameter names. MyPy covers the
configured core modules. Do not suppress a tool warning just to get a green check.

## Other formats and directory boundaries

`.editorconfig` uses LF, UTF-8 and final newlines; Python/shell/TOML use four-space
indentation, while JSON/YAML/CSS use two. Markdown headings/tables and fenced code
blocks should be consistent and resolve relative file links. `.gitattributes`
marks PNG/PDF as binary and normalizes project text without rewriting assets.

Keep runtime Python modules in the small flat root layout. Put tests under
`tests/`, standalone diagnostics under `scripts/`, synthetic fixtures/evaluator
under `evaluation/`, current guides under `docs/`, and dated evidence under
`docs/history/`. `research_papers/` is input data, `assets/` holds screenshots,
and hidden configuration directories retain their tool-defined locations.
Do not commit credentials, virtual environments, logs or generated FAISS state.

## Configuration boundaries

Adjustable provider endpoints, request limits, UI/context budgets and log
retention belong in validated Settings/environment entries with safe defaults.
Update `.env.sample`, [configuration reference](configuration.md), tests and
consumer wiring together. This project already uses `.env.sample`; a duplicate
`.env.example` with drifting defaults is unnecessary.

Keep file-format names/schema versions, protocol behavior, deterministic fixture
inputs and documented test thresholds in code when they define fixed contracts.
Compose service DNS names, mount layout and image versions remain infrastructure
configuration in Docker/Compose files, not duplicated as application settings.
Never move synthetic test credentials into live configuration or put real secrets
into examples. Adding a configuration option must not silently change its default.

## Required checks before a pull request

Run every command in [quality gates](quality-gates.md), including the consistency
checker and the Streamlit smoke. Run `uv lock --check`, shell syntax checks and
Compose/image validation when those files change. The inventory checker runs in
CI and requires an entry for every nonignored project file, including itself.
Review parsed JSON/TOML, local Markdown links and binary-file diffs before posting.

For configuration changes, prove both default preservation and nondefault values
at actual consumer boundaries with deterministic providers. Keep live-provider
quality and public deployment claims separate from provider-free evidence.
Do not merge a PR or claim all external integrations are validated merely because
CI passed. Document any validation that needs credentials or unavailable tooling.
