from __future__ import annotations

from pathlib import Path

import click
from dotenv import load_dotenv
from nexus.nexus_validator import NexusValidator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VALIDATOR_", extra="ignore")


class Validator(NexusValidator):
    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)


@click.command()
@click.option("--env-file", type=click.Path(exists=True, dir_okay=False, path_type=Path), default=None)
def main(env_file: Path | None) -> None:
    load_dotenv(env_file)
    Validator.run(settings_class=Settings)


if __name__ == "__main__":
    main()
