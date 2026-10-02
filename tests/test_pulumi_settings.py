import json
from typing import Annotated, Literal

import pytest
from pulumi import Output
from pydantic import Field, ValidationError

from pydantic_settings_pulumi.settings import PulumiConfigSource, PulumiSettings

FULL_BAG = {
    "project:enforcement": "active",
    "project:requiredChecks": '["preflight", "build"]',
    "project:limits": '{"maxRunners": 3}',
    "project:mergeBotAppId": "42",
    "project:mergeBotPrivateKey": "-----BEGIN PRIVATE KEY-----",
}


class SampleConfig(PulumiSettings):
    enforcement: Literal["active", "evaluate", "disabled"]
    required_checks: list[str]
    limits: dict[str, int]
    merge_bot_app_id: Annotated[int, Field(ge=1)]
    merge_bot_private_key: Output[str]


def test_plain_fields_read_camel_cased_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PULUMI_CONFIG", json.dumps(FULL_BAG))
    settings = SampleConfig.load()
    assert settings.enforcement == "active"
    assert settings.merge_bot_app_id == 42


def test_complex_fields_flow_parsed_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PULUMI_CONFIG", json.dumps(FULL_BAG))
    settings = SampleConfig.load()
    assert settings.required_checks == ["preflight", "build"]
    assert settings.limits == {"maxRunners": 3}


def test_secret_fields_are_outputs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PULUMI_CONFIG", json.dumps(FULL_BAG))
    settings = SampleConfig.load()
    assert isinstance(settings.merge_bot_private_key, Output)


def test_get_field_value_triple_carries_field_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PULUMI_CONFIG", json.dumps(FULL_BAG))
    source = PulumiConfigSource(SampleConfig)
    plain = SampleConfig.model_fields["merge_bot_app_id"]
    assert source.get_field_value(plain, "merge_bot_app_id") == ("42", "merge_bot_app_id", False)
    complex_field = SampleConfig.model_fields["required_checks"]
    assert source.get_field_value(complex_field, "required_checks") == (
        ["preflight", "build"],
        "required_checks",
        True,
    )


def test_absent_required_key_raises_field_named_error(monkeypatch: pytest.MonkeyPatch) -> None:
    incomplete = {key: value for key, value in FULL_BAG.items() if "PrivateKey" not in key}
    monkeypatch.setenv("PULUMI_CONFIG", json.dumps(incomplete))
    with pytest.raises(ValidationError) as excinfo:
        SampleConfig.load()
    assert "merge_bot_private_key" in str(excinfo.value)
