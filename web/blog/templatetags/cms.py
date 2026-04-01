from django import template

from blog.models import SiteText

register = template.Library()


@register.simple_tag
def cms_text(key: str, default: str = "") -> str:
    return SiteText.get_value(key, default)
