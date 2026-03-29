from django.urls import path

from . import views

urlpatterns = [
    path("signup/", views.signup_view, name="signup"),
    path("", views.account_dashboard, name="account_dashboard"),
    path("link/", views.link_telegram, name="account_link"),
    path("config/", views.account_config, name="account_config"),
    path("config/<int:subscription_id>/", views.account_config, name="account_config_id"),
    path("buy/", views.create_order_stub, name="account_buy"),
    path("renew/", views.create_order_stub, name="account_renew"),
    path("subscriptions/<int:subscription_id>/rename/", views.rename_subscription, name="account_subscription_rename"),
    path("subscriptions/<int:subscription_id>/revoke/", views.revoke_subscription, name="account_subscription_revoke"),
]
