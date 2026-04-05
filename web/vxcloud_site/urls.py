from django.contrib import admin
from django.urls import include, path, re_path
from django.views.generic import RedirectView

from blog import views as blog_views
from cabinet.views import (
    EmailLoginView,
    create_magic_link,
    open_app_link,
    payment_webhook,
    telegram_webapp_auth,
    tg_magic_login,
)

urlpatterns = [
    re_path(r"^admin(?:/.*)?$", RedirectView.as_view(url="/ops/", permanent=True)),
    path("ops/", include("backoffice.urls")),
    path("django-admin/", admin.site.urls),
    path("accounts/login/", EmailLoginView.as_view(), name="login"),
    path("accounts/", include("django.contrib.auth.urls")),
    path("api/auth/magic-link", create_magic_link, name="api_magic_link"),
    path("api/auth/telegram/webapp", telegram_webapp_auth, name="api_telegram_webapp_auth"),
    path("api/webhooks/<str:provider>", payment_webhook, name="api_payment_webhook"),
    path("auth/tg/<str:token>", tg_magic_login, name="tg_magic_login"),
    path("account-app/", include("cabinet.urls")),
    path("account/", include("cabinet.urls")),
    path("open-app/", open_app_link, name="open_app_link"),
    path("legacy/", include("blog.urls")),
    path("instructions/", blog_views.index, name="instructions"),
    path("", blog_views.home, name="home"),
    path("<path:path>/", blog_views.page_by_path, name="site_page"),
]
