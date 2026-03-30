from django.db import migrations


def _hero(title: str, subtitle: str) -> dict:
    return {"type": "hero", "value": {"title": title, "subtitle": subtitle}}


def _embed(url: str) -> dict:
    return {"type": "embed", "value": url}


def _howto(title: str) -> dict:
    return {
        "type": "howto_steps",
        "value": {
            "h2": "Пошагово",
            "steps": [
                {
                    "title_bold": "Шаг 1",
                    "text_rich": f"<p>{title}: добавьте сюда описание первого шага.</p>",
                    "image": None,
                    "alt_text": "",
                    "caption": "Скриншот шага 1",
                },
                {
                    "title_bold": "Шаг 2",
                    "text_rich": "<p>Опишите следующий шаг и прикрепите скриншот.</p>",
                    "image": None,
                    "alt_text": "",
                    "caption": "Скриншот шага 2",
                },
            ],
        },
    }


def _cta() -> dict:
    return {
        "type": "cta",
        "value": {
            "heading": "Нужна помощь?",
            "text": "Если что-то не получается, напишите в поддержку.",
            "button_text": "Открыть поддержку",
            "button_url": "/support/",
        },
    }


def _ensure_child(parent, page_model, model_cls, *, slug: str, title: str, intro: str, body: str = "", sections=None):
    existing_base = page_model.objects.filter(path__startswith=parent.path, depth=parent.depth + 1, slug=slug).first()
    if existing_base:
        existing = model_cls.objects.filter(id=existing_base.id).first()
        if not existing:
            return None
        changed = False
        if not (existing.intro or "").strip():
            existing.intro = intro
            changed = True
        if hasattr(existing, "body") and not (existing.body or "").strip() and body:
            existing.body = body
            changed = True
        if sections and not list(existing.sections or []):
            existing.sections = sections
            changed = True
        if changed:
            existing.save()
            existing.save_revision().publish()
        return existing

    page = model_cls(
        title=title,
        slug=slug,
        intro=intro,
        body=body,
        sections=sections or [],
        show_in_menus=False,
    )
    parent.add_child(instance=page)
    page.save_revision().publish()
    return page


def seed_help_pages(apps, schema_editor):
    Site = apps.get_model("wagtailcore", "Site")
    Page = apps.get_model("wagtailcore", "Page")
    CMSHomePage = apps.get_model("cms", "CMSHomePage")
    CMSContentPage = apps.get_model("cms", "CMSContentPage")

    site = Site.objects.filter(is_default_site=True).first() or Site.objects.first()
    if site:
        home = CMSHomePage.objects.filter(id=site.root_page_id).first()
    else:
        home = None

    if home is None:
        home = CMSHomePage.objects.first()
    if home is None:
        return

    help_sections = [
        _hero("Помощь VXcloud", "Выберите нужный сценарий и следуйте шагам ниже."),
        _cta(),
    ]
    help_page = _ensure_child(
        home,
        Page,
        CMSContentPage,
        slug="help",
        title="Help",
        intro="<p>База знаний по подключению и оплате.</p>",
        sections=help_sections,
    )
    if help_page is None:
        return

    install_sections = [
        _hero("Установка приложения", "Инструкция по установке и первому запуску."),
        _embed("https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
        _howto("Установка приложения"),
        _cta(),
    ]
    _ensure_child(
        help_page,
        Page,
        CMSContentPage,
        slug="install",
        title="Install",
        intro="<p>Как установить приложение для подключения.</p>",
        sections=install_sections,
    )

    stars_sections = [
        _hero("Оплата через Stars", "Как оплатить доступ через Telegram Stars."),
        _embed("https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
        _howto("Оплата через Stars"),
        _cta(),
    ]
    _ensure_child(
        help_page,
        Page,
        CMSContentPage,
        slug="stars",
        title="Stars",
        intro="<p>Пошагово про оплату Telegram Stars.</p>",
        sections=stars_sections,
    )

    connect_sections = [
        _hero("Подключение", "Как открыть доступ и подключиться по ссылке или QR."),
        _embed("https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
        _howto("Подключение"),
        _cta(),
    ]
    _ensure_child(
        help_page,
        Page,
        CMSContentPage,
        slug="connect",
        title="Connect",
        intro="<p>Инструкция по подключению после покупки.</p>",
        sections=connect_sections,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("cms", "0005_alter_sections_with_product_blocks"),
    ]

    operations = [
        migrations.RunPython(seed_help_pages, migrations.RunPython.noop),
    ]
