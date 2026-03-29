from wagtail.models import Site


def wagtail_navigation(request):
    pages = []
    try:
        site = Site.find_for_request(request)
        if site is not None and site.root_page is not None:
            pages = site.root_page.get_children().live().in_menu().specific()
    except Exception:
        pages = []
    return {"wagtail_menu_pages": pages}
