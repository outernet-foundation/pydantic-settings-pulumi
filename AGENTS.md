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

## Tests

`pulumi.Config()` outside the engine reads the `PULUMI_CONFIG` env var (JSON bag of
fully-qualified keys); the engine-less project name defaults to the literal `project`, so
test bags use `project:`-prefixed keys. `get_object` fields need the bag value to be a
JSON *string* (the getter JSON-parses it); `get_secret` works engine-less (the Output is
opaque — assert isinstance only, never resolve it). `SETTINGS.project` defaulting to
`"project"` was verified on pulumi 3.267.0; the pulumi floor pin is tied to that probe.

## Versioning

The pyproject version is real (no release-devkit sentinel patching — this package is not
devkit-managed and must not depend on the machinery it precedes). Publish flow: bump
pyproject, cut a GitHub release, `publish.yml` builds and publishes via trusted-publisher
OIDC. The operator owns repo creation, the PyPI trusted-publisher registration
(owner/repo/workflow binding to `publish.yml`), and releases.

## Verification

`uv run ruff check src/ tests/`, `uv run ruff format --check src/ tests/`,
`uv run basedpyright`, `uv run pytest` — all must be clean; CI runs the same battery in
`.github/workflows/integrate.yml`. `actionlint` on both workflow files.
