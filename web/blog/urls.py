from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="blog_home"),
    path("instructions/", views.index, name="blog_index"),
    path("instructions/category/<slug:slug>/", views.category_detail, name="blog_category_detail"),
    path("post/<slug:slug>/", views.post_detail, name="blog_post_detail"),
    path("page/<slug:slug>/", views.page_detail, name="blog_page_detail"),
]
