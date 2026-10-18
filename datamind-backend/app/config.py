from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=[ROOT / ".env", ROOT.parent / ".env"],
        extra="ignore",
    )

    snowflake_account: str = ""
    snowflake_user: str = ""
    snowflake_role: str = "DATAMIND_READER"
    snowflake_warehouse: str = "SNOWFLAKE_LEARNING_WH"
    snowflake_database: str = "SNOWFLAKE_SAMPLE_DATA"
    snowflake_schema: str = "TPCH_SF1"
    snowflake_private_key_path: Path = Path("~/.snowflake/datamind_key.p8")
    snowflake_private_key_passphrase: SecretStr | None = None
    llm_backend: Literal["ollama", "ai_studio"] = "ollama"
    google_api_key: SecretStr = SecretStr("")
    ai_studio_model: str = "gemma-4-26b-a4b-it"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "gemma3:12b"
    ollama_timeout_seconds: int = Field(default=180, ge=5, le=600)
    query_timeout_seconds: int = Field(default=30, ge=1, le=120)
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]
    api_key: SecretStr = SecretStr("")
    dataset_path: Path = ROOT / "datasets" / "tpch_orders.json"
    additional_dataset_paths: list[Path] = [ROOT / "datasets" / "worldbank_wdi.json"]
    history_path: Path = ROOT / "data" / "runs.sqlite3"
    # Off until audio/image are actually interpreted by Gemma; today the processor guesses from file names.
    enable_multimodal: bool = False

    @property
    def model_name(self) -> str:
        return self.ai_studio_model if self.llm_backend == "ai_studio" else self.ollama_model
