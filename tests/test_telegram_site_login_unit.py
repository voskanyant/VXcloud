import hashlib
import hmac
import os
import sys
import unittest
from contextlib import nullcontext
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = PROJECT_ROOT / "web"
if str(WEB_ROOT) not in sys.path:
    sys.path.append(str(WEB_ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "vxcloud_site.settings")

import django
from django.test import RequestFactory, override_settings

django.setup()

from unittest.mock import patch

from cabinet.views import _verify_telegram_login_payload, telegram_login


def _sign_telegram_login_payload(payload: dict[str, str], bot_token: str) -> str:
    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(payload.items()))
    secret_key = hashlib.sha256(bot_token.encode("utf-8")).digest()
    return hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()


class TelegramSiteLoginUnitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.factory = RequestFactory()

    def test_verify_telegram_login_payload_accepts_valid_signature(self):
        auth_date = "1712430000"
        payload = {
            "id": "777000",
            "first_name": "VX",
            "last_name": "Cloud",
            "username": "vxcloud_user",
            "auth_date": auth_date,
        }
        bot_token = "telegram-bot-token"
        signed_payload = dict(payload)
        signed_payload["hash"] = _sign_telegram_login_payload(payload, bot_token)

        with override_settings(
            TELEGRAM_WEBAPP_BOT_TOKEN=bot_token,
            TELEGRAM_LOGIN_AUTH_MAX_AGE_SECONDS=10**9,
        ):
            verified_data, error_code = _verify_telegram_login_payload(signed_payload)

        self.assertIsNone(error_code)
        self.assertIsNotNone(verified_data)
        assert verified_data is not None
        self.assertEqual(verified_data["telegram_id"], 777000)
        self.assertEqual(verified_data["telegram_username"], "vxcloud_user")
        self.assertEqual(verified_data["first_name"], "VX")
        self.assertEqual(verified_data["last_name"], "Cloud")

    def test_telegram_login_redirects_to_next_url_after_success(self):
        payload = {
            "id": "777000",
            "first_name": "VX",
            "last_name": "Cloud",
            "username": "vxcloud_user",
            "auth_date": "1712430000",
        }
        bot_token = "telegram-bot-token"
        signed_payload = dict(payload)
        signed_payload["hash"] = _sign_telegram_login_payload(payload, bot_token)
        signed_payload["next"] = "/account/config/42/"

        request = self.factory.get("/auth/telegram/login/", data=signed_payload)
        user = object()

        with override_settings(
            TELEGRAM_WEBAPP_BOT_TOKEN=bot_token,
            TELEGRAM_LOGIN_AUTH_MAX_AGE_SECONDS=10**9,
        ):
            with patch("cabinet.views.transaction.atomic", return_value=nullcontext()):
                with patch("cabinet.views._get_or_create_user_for_telegram", return_value=user) as get_user_mock:
                    with patch("cabinet.views.login") as login_mock:
                        response = telegram_login(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/account/config/42/")
        get_user_mock.assert_called_once_with(
            telegram_id=777000,
            telegram_username="vxcloud_user",
            first_name="VX",
            last_name="Cloud",
        )
        login_mock.assert_called_once_with(
            request,
            user,
            backend="django.contrib.auth.backends.ModelBackend",
        )

    def test_telegram_login_redirects_back_on_invalid_signature(self):
        request = self.factory.get(
            "/auth/telegram/login/",
            data={
                "id": "777000",
                "first_name": "VX",
                "auth_date": "1712430000",
                "hash": "0" * 64,
                "return_to": "/account/signup/",
            },
        )

        with override_settings(
            TELEGRAM_WEBAPP_BOT_TOKEN="telegram-bot-token",
            TELEGRAM_LOGIN_AUTH_MAX_AGE_SECONDS=10**9,
        ):
            with patch("cabinet.views.messages.error") as message_error_mock:
                with patch("cabinet.views.login") as login_mock:
                    response = telegram_login(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/account/signup/")
        message_error_mock.assert_called_once()
        login_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
