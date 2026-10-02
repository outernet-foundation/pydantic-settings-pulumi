# pydantic-settings-pulumi

Repo-agnostic conventions live in the workspace's `AGENTS-SHARED.md` (see the pulsar repo);
the summary: Python 3.13+, Ruff line-length 120, basedpyright strict, no docstrings, no
inline imports, comments rare and self-contained. This file is package-specific.

## What this is

A pydantic-settings source for Pulumi programs, extracted from infra-github-org's config
adapter (plan-infra-reorg.md Phase A2). Public surface is exactly two names:
`PulumiConfigSource` and `PulumiSettings`, both defined in `settings.py` — `__init__.py`
is ALWAYS empty (operator ruling; consumers import the submodule and accept the longer
spelling). Consumers are standalone Pulumi repos that pin a version floor (`>=`) and rely
on their uv.lock; `OrgConfig`-style concrete configs stay in each consumer —
census-specific fields never move here.

## The quirks this package owns

- **The ABC triple contract.** `get_field_value` returns `(value, field_name, is_complex)`
  — the second element MUST be the field name, not the derived camelCase config key. The
  inherited env-source assembly loop uses it as the model-creation key; returning the
  config key makes construction die with missing/extra_forbidden errors. The regression
  test asserts the triple directly.
- **The `__init__` shim / pyright synthesis interaction.** The explicit
  `def __init__(self, **values)` exists only to stop pyright's `@dataclass_transform`
  synthesis from demanding constructor args the source fills. It only works on the class
  that DECLARES it — inherited, the synthesis returns — so `load()` (whose `cls()` call
  typechecks against the bound's explicit `__init__`) is the sanctioned constructor for
  subclasses.
- **The two re-export import paths.** `FieldInfo` imports from `pydantic.fields` and
  `PydanticBaseEnvSettingsSource` from `pydantic_settings.sources` — the top-level
  re-exports resolve to Unknown under basedpyright strict. Do not "simplify" them.
- **The three model_config flags** (`arbitrary_types_allowed`, `case_sensitive=True`,
  `enable_decoding=False`) are load-bearing as a set; see README for what each
  neutralizes. Removing any one kills subclass construction.
- **Secret fields are `Output[str]` annotations** routed to `get_secret` by
  `get_origin(field.annotation) is Output` — the branch ordering in `get_field_value`
  matters: `get_origin` on a plain annotation is `None`, so the Output and list/dict
  branches precede the plain-get fallback.
- **The `settings_customise_sources` signature is fixed by pydantic-settings** —
  the library calls the hook with keyword arguments, so the four source parameter
  names are load-bearing and the three declined sources must stay declared
  (underscore-prefixing dies at construction with a TypeError). `@typing.override`
  (PEP 698) marks the method as an override: ruff's unused-argument rules exempt
  `@override`-decorated methods, and pyright verifies the hook still exists
  upstream — no suppression layer (`ruff.toml` is a bare extend).

## Tests

`pulumi.Config()` outside the engine reads the `PULUMI_CONFIG` env var (JSON bag of
fully-qualified keys); the engine-less project name defaults to the literal `project`, so
test bags use `project:`-prefixed keys. `get_object` fields need the bag value to be a
JSON *string* (the getter JSON-parses it); `get_secret` works engine-less (the Output is
opaque — assert isinstance only, never resolve it). `SETTINGS.project` defaulting to
`"project"` was verified on pulumi 3.267.0; the pulumi floor pin is tied to that probe.
The toolchain is pinned to 3.13 (`.python-version`): engine-less `Output` construction
hard-fails on 3.14 (`asyncio.get_event_loop()` raises without a running loop); a bump
past 3.13 must re-probe that first.

## Release flow

Org-standard release-devkit consumption, same shape as every other python repo. The
committed `pyproject.toml` version is permanently the `0.0.0.dev0` sentinel; versions
ride the declared `major_minor` line (`"0.1"` in `release-devkit.yaml`) on the
`pydantic-settings-pulumi-v*` tag ledger. Two workflow files split by triggering event:
`integrate.yml` (PR to `dev` + dispatch) runs `preflight` — ledger checkout,
the `setup-release-devkit` wrapper, the `lint-ci` run step, then
`uv run preflight-python` (python-devkit lives in the dev group; this repo is an
ordinary consumer, not a name-shadowing case like bashrun/ci-devkit, so no
`tools/devkit` sidecar) and the `publish-stable --dry-run` run step as the trailing
step. `publish.yml` (push to `main`/`dev`, concurrency queues without cancel)
runs `ensure-release-pr` and `publish-prerelease` on `dev`, `publish-stable` on `main`,
under OIDC trusted publishing (publisher bound to `publish.yml`, `release` environment).
The devkit is installed onto the machine by the wrapper —
`.github/actions/setup-release-devkit/action.yml`, the one place the pinned devkit
commit SHA appears: setup-uv, then a tokenless `git clone` into
`$RUNNER_TEMP/release-devkit` (outside the workspace, so this repo's own deptry/ruff
battery never scans devkit code). Verbs are plain run steps —
`uv run --project "$RUNNER_TEMP/release-devkit" --locked --no-dev <verb>` from the
repo root, with the env each verb needs (`GH_TOKEN`, `CI_REGISTRY_*`) spelled in the
step. Publishing to PyPI is the devkit's
`PyPIRegistry` (`uv build` + `uv publish` with `--check-url` idempotency) — never inline
`uv build`/publish steps here. The operator owns the initial trusted-publisher
registration and every push.

## Verification

`uv run preflight-python` — the org's fixed battery (sync, ruff check, ruff format,
basedpyright, deptry, lock staleness, ruff drift, pytest) — must pass; CI runs the same
command in `integrate.yml`. `actionlint` on both workflow files. `ruff.base.toml` is
verb-written from python-devkit's canonical config — regenerate with
`uvx --from python-devkit sync-ruff`, never hand-edit it; repo-local ruff deltas go in
`ruff.toml` using extend-key forms only.
