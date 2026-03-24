from urllib.parse import urlencode, quote


def build_vless_url(
    *,
    uuid: str,
    host: str,
    port: int,
    tag: str,
    public_key: str,
    short_id: str,
    sni: str,
    fingerprint: str = "chrome",
    flow: str = "xtls-rprx-vision",
) -> str:
    params = {
        "encryption": "none",
        "type": "tcp",
        "security": "reality",
        "pbk": public_key,
        "fp": fingerprint,
        "sni": sni,
        "sid": short_id,
        "flow": flow,
    }
    query = urlencode(params, safe="")
    return f"vless://{uuid}@{host}:{port}?{query}#{quote(tag)}"
