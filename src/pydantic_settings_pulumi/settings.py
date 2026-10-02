from typing import Any, Self, get_origin

from pulumi import Config, Output
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict
from pydantic_settings.sources import PydanticBaseEnvSettingsSource

__all__ = ["PulumiConfigSource", "PulumiSettings"]


class PulumiConfigSource(PydanticBaseEnvSettingsSource):
    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        project_config = Config()
        head, *tail = field_name.split("_")
        key = head + "".join(part.title() for part in tail)
        if get_origin(field.annotation) is Output:
            return project_config.get_secret(key), field_name, False
        if get_origin(field.annotation) in (list, dict):
            return project_config.get_object(key), field_name, True
        return project_config.get(key), field_name, False


class PulumiSettings(BaseSettings):
    model_config = SettingsConfigDict(
        arbitrary_types_allowed=True,
        case_sensitive=True,
        enable_decoding=False,
    )

    def __init__(self, **values: Any) -> None:
        super().__init__(**values)

    @classmethod
    def load(cls) -> Self:
        return cls()

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (init_settings, PulumiConfigSource(settings_cls))
