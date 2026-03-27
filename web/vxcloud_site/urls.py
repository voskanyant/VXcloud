from django.contrib import admin
from django.urls import include, path
from cabinet.views import open_app_link
from wagtail import urls as wagtail_urls
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.documents import urls as wagtaildocs_urls

urlpatterns = [
    path("admin/", admin.site.urls),
    path("cms-admin/", include(wagtailadmin_urls)),
    path("cms-documents/", include(wagtaildocs_urls)),
    path("accounts/", include("django.contrib.auth.urls")),
    path("account/", include("cabinet.urls")),
    path("open-app/", open_app_link, name="open_app_link"),
    path("legacy/", include("blog.urls")),
    path("", include(wagtail_urls)),
]
