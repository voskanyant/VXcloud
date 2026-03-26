from django.contrib import admin
from django.urls import include, path
from cabinet.views import open_app_link

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("account/", include("cabinet.urls")),
    path("open-app/", open_app_link, name="open_app_link"),
    path("", include("blog.urls")),
]
