import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = PROJECT_ROOT / "web"
if str(WEB_ROOT) not in sys.path:
    sys.path.append(str(WEB_ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "vxcloud_site.settings")

import django

django.setup()

from django.contrib.auth.models import User
from django.db import DatabaseError
from django.test import Client


class AccountProfileUpdateUnitTests(unittest.TestCase):
    def setUp(self) -> None:
        User.objects.filter(
            username__in=[
                "profile_update_user",
                "profile_update_user_new",
                "profile_update_taken",
            ]
        ).delete()
        User.objects.filter(
            email__in=[
                "profile_update_user@example.com",
                "profile_update_user_new@example.com",
                "profile_update_taken@example.com",
            ]
        ).delete()

        self.user, _ = User.objects.get_or_create(
            username="profile_update_user",
            defaults={
                "email": "profile_update_user@example.com",
                "first_name": "Old",
                "last_name": "Name",
            },
        )
        self.user.set_password("pass12345")
        self.user.save()

        self.other_user, _ = User.objects.get_or_create(
            username="profile_update_taken",
            defaults={"email": "profile_update_taken@example.com"},
        )

        self.client = Client()
        assert self.client.login(username="profile_update_user", password="pass12345")

    def test_profile_update_succeeds_even_if_bot_sync_fails(self):
        payload = {
            "username": "profile_update_user_new",
            "email": "profile_update_user_new@example.com",
            "first_name": "Tigran",
            "last_name": "Voskanyan",
        }

        with patch("cabinet.views._ensure_site_bot_user", side_effect=DatabaseError("users table unavailable")):
            response = self.client.post(
                "/account-app/api/profile/",
                data=payload,
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["user"]["username"], payload["username"])
        self.assertEqual(body["user"]["email"], payload["email"])
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, payload["username"])
        self.assertEqual(self.user.email, payload["email"])
        self.assertEqual(self.user.first_name, payload["first_name"])
        self.assertEqual(self.user.last_name, payload["last_name"])

    def test_profile_update_rejects_duplicate_email_and_username(self):
        payload = {
            "username": self.other_user.username,
            "email": self.other_user.email,
            "first_name": "",
            "last_name": "",
        }

        with patch("cabinet.views._ensure_site_bot_user", return_value=None):
            response = self.client.post(
                "/account-app/api/profile/",
                data=payload,
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertFalse(body["ok"])
        self.assertIn("username", body["errors"])
        self.assertIn("email", body["errors"])


if __name__ == "__main__":
    unittest.main()
