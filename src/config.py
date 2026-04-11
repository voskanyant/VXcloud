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


def _normalize_sub_path(raw: str | None) -> str:
    value = str(raw or "").strip() or "/sub"
    if not value.startswith("/"):
        value = f"/{value}"
    value = value.rstrip("/")
    return value or "/sub"


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
    vpn_cluster_enabled: bool
    vpn_cluster_healthcheck_interval_seconds: int
    vpn_cluster_sync_interval_seconds: int
    vpn_cluster_sync_batch_size: int
    vpn_tag: str
    vpn_flow: str
    plan_days: int
    plan_price_stars: int
    card_payment_amount_minor: int
    card_payment_currency: str
    max_devices_per_sub: int
    price_text: str
    timezone: str
    cms_base_url: str | None
    cms_token: str | None
    cms_content_collection: str
    cms_button_collection: str
    cms_cache_ttl_seconds: int
    magic_link_shared_secret: str | None
    magic_link_api_timeout_seconds: int
    enforce_single_ip: bool
    single_ip_check_interval_seconds: int
    single_ip_window_seconds: int
    single_ip_block_seconds: int
    xray_access_log_path: str
    xui_sub_path: str = "/sub"

    @classmethod
    def from_env(cls) -> "Settings":
        return load_settings()


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
        vpn_cluster_enabled=_get("VPN_CLUSTER_ENABLED", "0").strip() == "1",
        vpn_cluster_healthcheck_interval_seconds=int(_get("VPN_CLUSTER_HEALTHCHECK_INTERVAL_SECONDS", "30")),
        vpn_cluster_sync_interval_seconds=int(_get("VPN_CLUSTER_SYNC_INTERVAL_SECONDS", "60")),
        vpn_cluster_sync_batch_size=int(_get("VPN_CLUSTER_SYNC_BATCH_SIZE", "200")),
        vpn_tag=_get("VPN_TAG", "VPN"),
        vpn_flow=_get("VPN_FLOW", "xtls-rprx-vision"),
        plan_days=int(_get("PLAN_DAYS", "30")),
        plan_price_stars=int(_get("PLAN_PRICE_STARS", "250")),
        card_payment_amount_minor=int(_get("CARD_PAYMENT_AMOUNT_MINOR", "24900")),
        card_payment_currency=_get("CARD_PAYMENT_CURRENCY", "RUB").upper(),
        max_devices_per_sub=int(_get("MAX_DEVICES_PER_SUB", "1")),
        price_text=_get("PRICE_TEXT", "Monthly plan"),
        timezone=_get("TIMEZONE", "UTC"),
        cms_base_url=_get_optional("CMS_BASE_URL"),
        cms_token=_get_optional("CMS_TOKEN"),
        cms_content_collection=_get("CMS_CONTENT_COLLECTION", "bot_content"),
        cms_button_collection=_get("CMS_BUTTON_COLLECTION", "bot_buttons"),
        cms_cache_ttl_seconds=int(_get("CMS_CACHE_TTL_SECONDS", "60")),
        magic_link_shared_secret=_get_optional("MAGIC_LINK_SHARED_SECRET"),
        magic_link_api_timeout_seconds=int(_get("MAGIC_LINK_API_TIMEOUT_SECONDS", "5")),
        enforce_single_ip=_get("ENFORCE_SINGLE_IP", "0").strip() == "1",
        single_ip_check_interval_seconds=int(_get("SINGLE_IP_CHECK_INTERVAL_SECONDS", "20")),
        single_ip_window_seconds=int(_get("SINGLE_IP_WINDOW_SECONDS", "90")),
        single_ip_block_seconds=int(_get("SINGLE_IP_BLOCK_SECONDS", "120")),
        xray_access_log_path=_get("XRAY_ACCESS_LOG_PATH", "/var/log/xray/access.log"),
        xui_sub_path=_normalize_sub_path(_get("XUI_SUB_PATH", "/sub")),
    )
