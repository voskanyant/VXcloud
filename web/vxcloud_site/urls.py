from django.contrib import admin
from django.urls import include, path

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
    path("admin/", include("backoffice.urls")),
    path("django-admin/", admin.site.urls),
    path("accounts/login/", EmailLoginView.as_view(), name="login"),
    path("accounts/", include("django.contrib.auth.urls")),
    path("api/auth/magic-link", create_magic_link, name="api_magic_link"),
    path("api/auth/telegram/webapp", telegram_webapp_auth, name="api_telegram_webapp_auth"),
    path("api/webhooks/<str:provider>", payment_webhook, name="api_payment_webhook"),
    path("auth/tg/<str:token>", tg_magic_login, name="tg_magic_login"),
    path("account/", include("cabinet.urls")),
    path("open-app/", open_app_link, name="open_app_link"),
    path("legacy/", include("blog.urls")),
    path("instructions/", blog_views.index, name="instructions"),
    path("blog/", blog_views.page_by_path, {"path": "blog"}, name="blog_index"),
    path("blog/category/<slug:slug>/", blog_views.category_detail, name="blog_category_detail"),
    path("blog/<slug:slug>/", blog_views.post_detail, name="blog_post_detail"),
    path("", blog_views.home, name="home"),
    path("<path:path>/", blog_views.page_by_path, name="site_page"),
]
