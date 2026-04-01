from django.core.management.base import BaseCommand

from blog.models import Page


DEFAULT_PAGES = [
    {
        "slug": "home",
        "path": "/",
        "title": "VXcloud",
        "summary": "Стабильный доступ к интернету для работы и повседневных задач.",
        "content": "<p>Оформите доступ в личном кабинете и подключитесь за пару минут.</p>",
        "is_homepage": True,
        "show_in_nav": True,
        "nav_title": "Главная",
        "nav_order": 10,
    },
    {
        "slug": "how-it-works",
        "path": "/how-it-works/",
        "title": "Как это работает",
        "summary": "Простая схема: оплата, получение доступа, подключение.",
        "content": "<p>1. Оплатите доступ в личном кабинете.</p><p>2. Получите ссылку и QR-код.</p><p>3. Подключитесь в приложении.</p>",
        "show_in_nav": True,
        "nav_title": "Как это работает",
        "nav_order": 20,
    },
    {
        "slug": "help",
        "path": "/help/",
        "title": "Инструкции",
        "summary": "Пошаговые инструкции по установке и подключению.",
        "content": "<p>Установка приложения, оплата и подключение описаны по шагам.</p>",
        "show_in_nav": True,
        "nav_title": "Инструкции",
        "nav_order": 30,
    },
    {
        "slug": "faq",
        "path": "/faq/",
        "title": "FAQ",
        "summary": "Ответы на частые вопросы.",
        "content": "<p>Если не нашли ответ, напишите в поддержку.</p>",
        "show_in_nav": True,
        "nav_title": "FAQ",
        "nav_order": 40,
    },
    {
        "slug": "blog",
        "path": "/blog/",
        "title": "Блог",
        "summary": "Публикации и полезные материалы.",
        "content": "<p>Новые статьи и инструкции.</p>",
        "show_in_nav": True,
        "nav_title": "Блог",
        "nav_order": 50,
        "posts_enabled": True,
        "posts_source": "all",
        "posts_title": "Публикации",
        "posts_limit": 24,
    },
    {
        "slug": "services",
        "path": "/services/",
        "title": "Услуги и тарифы",
        "summary": "Описание услуг VXcloud и актуальной стоимости.",
        "content": "<p>Базовый тариф: 30 дней доступа — <strong>249 ₽</strong>.</p>",
        "show_in_nav": False,
    },
    {
        "slug": "delivery",
        "path": "/delivery/",
        "title": "Доставка и получение",
        "summary": "Порядок получения цифрового доступа после оплаты.",
        "content": "<p>Услуга цифровая, физическая доставка отсутствует.</p>",
        "show_in_nav": False,
    },
    {
        "slug": "terms",
        "path": "/terms/",
        "title": "Условия использования",
        "summary": "Публичная оферта и условия предоставления доступа.",
        "content": "<p>Разместите здесь актуальные юридические условия.</p>",
        "show_in_nav": False,
    },
    {
        "slug": "privacy",
        "path": "/privacy/",
        "title": "Политика конфиденциальности",
        "summary": "Правила обработки персональных данных.",
        "content": "<p>Разместите здесь актуальную политику обработки данных.</p>",
        "show_in_nav": False,
    },
    {
        "slug": "contacts",
        "path": "/contacts/",
        "title": "Контакты и реквизиты",
        "summary": "Контакты поддержки и юридические реквизиты.",
        "content": "<p>Email: support@vxcloud.ru</p><p>Telegram: @VXcloud_rubot</p>",
        "show_in_nav": False,
    },
]


class Command(BaseCommand):
    help = "Create default editable site pages in Django Admin CMS."

    def handle(self, *args, **options):
        for item in DEFAULT_PAGES:
            defaults = {
                "title": item["title"],
                "summary": item["summary"],
                "content": item["content"],
                "is_homepage": item.get("is_homepage", False),
                "show_in_nav": item.get("show_in_nav", False),
                "nav_title": item.get("nav_title", ""),
                "nav_order": item.get("nav_order", 50),
                "is_published": True,
                "posts_enabled": item.get("posts_enabled", False),
                "posts_source": item.get("posts_source", "all"),
                "posts_title": item.get("posts_title", "Публикации"),
                "posts_limit": item.get("posts_limit", 24),
            }
            page, _ = Page.objects.update_or_create(slug=item["slug"], defaults=defaults | {"path": item["path"]})
            self.stdout.write(self.style.SUCCESS(f"ready: {page.path}"))
