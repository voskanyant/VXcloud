from django.urls import path

from . import views

urlpatterns = [
    path("feed/<str:feed_token>/", views.account_subscription_feed, name="account_subscription_feed"),
    path("api/state/", views.account_api_state, name="account_api_state"),
    path("api/login/", views.account_api_login, name="account_api_login"),
    path("api/signup/", views.account_api_signup, name="account_api_signup"),
    path("api/logout/", views.account_api_logout, name="account_api_logout"),
    path("api/profile/", views.account_api_profile, name="account_api_profile"),
    path("api/link/", views.account_api_link, name="account_api_link"),
    path("api/buy/", views.account_api_buy, name="account_api_buy"),
    path("api/renew/", views.account_api_renew, name="account_api_renew"),
    path("api/subscriptions/<int:subscription_id>/rename/", views.account_api_rename_subscription, name="account_api_subscription_rename"),
    path("api/subscriptions/<int:subscription_id>/delete/", views.account_api_delete_subscription, name="account_api_subscription_delete"),
    path("signup/", views.signup_view, name="signup"),
    path("", views.account_dashboard, name="account_dashboard"),
    path("link/", views.link_telegram, name="account_link"),
    path("config/", views.account_config, name="account_config"),
    path("config/<int:subscription_id>/", views.account_config, name="account_config_id"),
    path("buy/", views.create_order_stub, name="account_buy"),
    path("renew/", views.create_order_stub, name="account_renew"),
    path("subscriptions/<int:subscription_id>/rename/", views.rename_subscription, name="account_subscription_rename"),
    path("subscriptions/<int:subscription_id>/revoke/", views.revoke_subscription, name="account_subscription_revoke"),
    path("subscriptions/<int:subscription_id>/delete/", views.delete_subscription, name="account_subscription_delete"),
]
