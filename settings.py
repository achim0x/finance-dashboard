"""Application settings via pydantic-settings.

All values come from environment variables / the `.env` file (see
`.env.example` and spec §11). Provider routing, credentials and polling
intervals configured here act only as bootstrap/fallback defaults; the
authoritative runtime configuration lives in the `KursEinstellung` /
`WaehrungsEinstellung` entities maintained through the setup page (spec §6.6).
"""
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Database & app ---
    db_backend: Literal["sqlite", "mariadb"] = Field(default="sqlite")
    db_url: str = Field(default="sqlite:///./musterdepot.sqlite")
    secret_key: str = Field(default="dev-only-change-me")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")

    # --- i18n (REQ-I18N): default UI language; German is the first
    # fully implemented language. ---
    default_sprache: str = Field(default="de")

    # --- Domain behaviour ---
    # Allow the cash balance to go negative on buys/withdrawals (spec §5.2).
    barbestand_ueberziehen_erlauben: bool = Field(default=False)
    # Cost matching method for realized gains (spec §5.3).
    verrechnungsmethode: Literal["FIFO", "DURCHSCHNITT"] = Field(default="FIFO")

    # --- Encryption of provider credentials stored in the DB (spec §6.6).
    # The key lives only in the environment, never in the database. ---
    credentials_enc_key: str = Field(default="")

    # --- Price providers (bootstrap/fallback defaults, spec §11) ---
    provider_aktien_etf: str = Field(default="fmp")
    provider_hebelprodukt: str = Field(default="pytr")
    kurs_cache_ttl: int = Field(default=60)  # seconds

    # FMP (used for stock/ETF quotes and FX rates)
    fmp_api_key: str = Field(default="")

    # FX provider (bootstrap default; runtime config via setup page, spec §6.10)
    fx_provider: str = Field(default="fmp")

    # pytr / Trade Republic (secrets — never log these; spec §6.4)
    pytr_phone_no: str = Field(default="")
    pytr_pin: str = Field(default="")
    pytr_keyfile: str = Field(default="")

    # --- MCP server (static bearer key, spec §9) ---
    musterdepot_mcp_key: str = Field(default="")
    musterdepot_mcp_host: str = Field(default="127.0.0.1")
    musterdepot_mcp_port: int = Field(default=8000)

    # --- Testing/tooling ---
    seed_on_startup: bool = Field(default=False)
