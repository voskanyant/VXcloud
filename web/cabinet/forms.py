from __future__ import annotations

from django import forms


class SignUpForm(forms.Form):
    username = forms.CharField(max_length=150)
    password = forms.CharField(widget=forms.PasswordInput)


class LinkTelegramForm(forms.Form):
    telegram_id = forms.IntegerField(min_value=1)
