from django.urls import path

from . import views

urlpatterns = [
    path("signup/", views.signup_view, name="signup"),
    path("", views.account_dashboard, name="account_dashboard"),
    path("link/", views.link_telegram, name="account_link"),
    path("config/", views.account_config, name="account_config"),
    path("renew/", views.create_order_stub, name="account_renew"),
]
