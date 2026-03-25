from dataclasses import dataclass
import os

from dotenv import load_dotenv


load_dotenv()


def _get(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def _get_optional(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed if trimmed else None


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    telegram_admin_id: int
    database_url: str
    xui_base_url: str
    xui_username: str
    xui_password: str
    xui_inbound_id: int
    xui_sub_port: int
    vpn_public_host: str
    vpn_public_port: int
    vpn_tag: str
    plan_days: int
    plan_price_stars: int
    price_text: str
    timezone: str
    cms_base_url: str | None
    cms_token: str | None
    cms_content_collection: str
    cms_button_collection: str
    cms_cache_ttl_seconds: int


def load_settings() -> Settings:
    return Settings(
        telegram_bot_token=_get("TELEGRAM_BOT_TOKEN"),
        telegram_admin_id=int(_get("TELEGRAM_ADMIN_ID", "0")),
        database_url=_get("DATABASE_URL"),
        xui_base_url=_get("XUI_BASE_URL").rstrip("/"),
        xui_username=_get("XUI_USERNAME"),
        xui_password=_get("XUI_PASSWORD"),
        xui_inbound_id=int(_get("XUI_INBOUND_ID")),
        xui_sub_port=int(_get("XUI_SUB_PORT", "2096")),
        vpn_public_host=_get("VPN_PUBLIC_HOST"),
        vpn_public_port=int(_get("VPN_PUBLIC_PORT")),
        vpn_tag=_get("VPN_TAG", "VPN"),
        plan_days=int(_get("PLAN_DAYS", "30")),
        plan_price_stars=int(_get("PLAN_PRICE_STARS", "250")),
        price_text=_get("PRICE_TEXT", "Monthly plan"),
        timezone=_get("TIMEZONE", "UTC"),
        cms_base_url=_get_optional("CMS_BASE_URL"),
        cms_token=_get_optional("CMS_TOKEN"),
        cms_content_collection=_get("CMS_CONTENT_COLLECTION", "bot_content"),
        cms_button_collection=_get("CMS_BUTTON_COLLECTION", "bot_buttons"),
        cms_cache_ttl_seconds=int(_get("CMS_CACHE_TTL_SECONDS", "60")),
    )
