from django import template

from blog.models import SiteText

register = template.Library()


@register.simple_tag
def cms_text(key: str, default: str = "") -> str:
    from cms.models import SiteCopy

    if SiteCopy.objects.filter(key=key).exists():
        return SiteCopy.get_text(key, default="")
    return SiteText.get_value(key, default)
