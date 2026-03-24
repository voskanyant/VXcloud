from dataclasses import dataclass
import os

from dotenv import load_dotenv


load_dotenv()


def _get(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    telegram_admin_id: int
    database_url: str
    xui_base_url: str
    xui_username: str
    xui_password: str
    xui_inbound_id: int
    vpn_public_host: str
    vpn_public_port: int
    vpn_tag: str
    plan_days: int
    price_text: str
    timezone: str


def load_settings() -> Settings:
    return Settings(
        telegram_bot_token=_get("TELEGRAM_BOT_TOKEN"),
        telegram_admin_id=int(_get("TELEGRAM_ADMIN_ID", "0")),
        database_url=_get("DATABASE_URL"),
        xui_base_url=_get("XUI_BASE_URL").rstrip("/"),
        xui_username=_get("XUI_USERNAME"),
        xui_password=_get("XUI_PASSWORD"),
        xui_inbound_id=int(_get("XUI_INBOUND_ID")),
        vpn_public_host=_get("VPN_PUBLIC_HOST"),
        vpn_public_port=int(_get("VPN_PUBLIC_PORT")),
        vpn_tag=_get("VPN_TAG", "VPN"),
        plan_days=int(_get("PLAN_DAYS", "30")),
        price_text=_get("PRICE_TEXT", "Monthly plan"),
        timezone=_get("TIMEZONE", "UTC"),
    )
