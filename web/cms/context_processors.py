from wagtail.models import Site


def wagtail_navigation(request):
    pages = []
    blog_categories = []
    try:
        site = Site.find_for_request(request)
        if site is not None and site.root_page is not None:
            pages = site.root_page.get_children().live().in_menu().specific()
    except Exception:
        pages = []
    try:
        from blog.models import Category

        blog_categories = list(Category.objects.filter(is_active=True).order_by("title"))
    except Exception:
        blog_categories = []
    return {"wagtail_menu_pages": pages, "blog_categories": blog_categories}
