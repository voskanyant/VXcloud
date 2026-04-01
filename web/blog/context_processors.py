from .models import Page


def site_navigation(request):
    nav_pages = Page.objects.filter(is_published=True, show_in_nav=True).order_by("nav_order", "id")
    return {"nav_pages": nav_pages}
