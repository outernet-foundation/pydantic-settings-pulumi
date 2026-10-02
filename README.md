# pydantic-settings-pulumi

A [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) source
for Pulumi programs: declare your stack config as a typed settings class instead of
per-key `pulumi.Config` getter calls.

Pulumi's Python SDK offers no modeling layer for program configuration — `pulumi.Config`
is per-key coercing getters and an unvalidated-`Any` `get_object`. This package turns a
stack's config into what it already is in the yaml: a typed object. Field annotations are
the whole declaration (`Literal[...]` enums, `Field(ge=1)`, `min_length`), config keys
derive from field names by camelCasing, and a bad value dies at preview with a
field-named pydantic error.

```python
from pulumi import Output
from pydantic import Field
from typing import Annotated, Literal
from pydantic_settings_pulumi.settings import PulumiSettings


class OrgConfig(PulumiSettings):
    dev_ruleset_enforcement: Literal["active", "evaluate", "disabled"]
    dev_ruleset_required_checks: Annotated[list[str], Field(min_length=1)]
    merge_bot_app_id: Annotated[int, Field(ge=1)]
    merge_bot_private_key: Output[str]


settings = OrgConfig.load()
```

Given `Pulumi.dev.yaml` keys `devRulesetEnforcement`, `devRulesetRequiredChecks`,
`mergeBotAppId` and secret `mergeBotPrivateKey` (all project-namespace, no prefix). A new
config key is one field declaration, nothing else.

## The constructor is `load()`

`PulumiSettings.load()` is the sanctioned constructor. `OrgConfig()` also works at
runtime, but pyright's `@dataclass_transform` synthesis demands constructor args for
required fields even though the source fills them — the synthesis-stopping `__init__`
shim only works on the class that declares it, so subclass construction typechecks
through `load()` only.

## Secrets are `Output[str]` fields

One line per secret, no accessors: an `Output[str]`-annotated field routes through
`pulumi.Config.get_secret`, so the value arrives as a secret `Output` and the plaintext
never reaches the program. Validation is necessarily isinstance-only. This requires
`arbitrary_types_allowed`, one of the three flags `PulumiSettings.model_config` sets on
your behalf:

- `arbitrary_types_allowed=True` — permits the `Output` annotations.
- `case_sensitive=True` — disables pydantic-settings' inherited case-folding machinery,
  which is meaningless when the only source reads exact Pulumi keys.
- `enable_decoding=False` — the inherited env-source assembly loop JSON-decodes
  complex-typed field values; Pulumi's `get_object` already returns parsed values.

Remove any of the three and construction dies.

## Types and defaults still belong to the platform

Where `Pulumi.yaml`'s `config:` spec block can express a type or a default, let it: the
CLI validates every stack value and supplies defaults before the program runs. The
annotations carry what the platform cannot — enums, positivity, non-emptiness.

## Testing consumers

`pulumi.Config()` outside the engine reads the `PULUMI_CONFIG` env var — a JSON bag of
fully-qualified keys. Outside the engine the project name defaults to the literal
`project`, so a test bag looks like:

```python
os.environ["PULUMI_CONFIG"] = json.dumps({
    "project:mergeBotAppId": "42",
    "project:mergeBotPrivateKey": "dummy",
    "project:requiredChecks": '["preflight"]',  # get_object JSON-parses string values
})
```

## Versioning and publishing

The committed `pyproject.toml` version is permanently the `0.0.0.dev0` sentinel; real
versions come from the `pydantic-settings-pulumi-v*` tag ledger (declared `major_minor`
line in `release-devkit.yaml`, patch-auto within the line). Publishing rides the org's
release-devkit machinery, like every other python repo: pushes to `dev` publish
immutable `-dev.<run-id>` prereleases, a standing release PR gates `dev` → `main`, and
a merge to `main` publishes the stable version, tags it, and cuts the GitHub Release —
via trusted-publisher OIDC (publisher bound to `publish.yml`), no stored tokens.

## Why a separate package

Nothing equivalent exists: pydantic-settings' own source family (env, dotenv, cli,
secrets-dir, json, toml, yaml, pyproject, cloud-store extras) has no Pulumi member, and
Pulumi ships no typed program-side config. The name follows the
`pydantic-settings-aws` precedent for third-party sources. Upstreaming into
pydantic-settings later remains open; this package is the proving ground.
