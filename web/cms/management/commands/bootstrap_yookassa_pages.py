from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand
from wagtail.models import Page, Site

from cms.models import CMSContentPage, CMSHomePage


class Command(BaseCommand):
    help = "Create/update Wagtail pages required for YooKassa website moderation."

    def handle(self, *args: Any, **options: Any) -> None:
        root = Page.get_first_root_node()
        home = CMSHomePage.objects.live().first() or CMSHomePage.objects.first()
        if home is None:
            home = CMSHomePage(
                title="Главная",
                slug="glavnaya",
                intro="<p>Стабильный доступ к интернету для работы и общения.</p>",
                show_in_menus=True,
            )
            root.add_child(instance=home)
            home.save_revision().publish()
            self.stdout.write(self.style.SUCCESS(f"Created home page: {home.slug}"))
        else:
            if not home.live:
                home.save_revision().publish()
            if not home.show_in_menus:
                home.show_in_menus = True
                home.save(update_fields=["show_in_menus"])
            self.stdout.write(self.style.SUCCESS(f"Using home page: {home.slug}"))

        self._ensure_site(home, "vxcloud.ru", is_default=True)
        self._ensure_site(home, "www.vxcloud.ru", is_default=False)

        how_it_works = self._ensure_page(
            parent=home,
            title="Как это работает",
            slug="how-it-works",
            show_in_menus=True,
            intro="<p>Кратко: выберите тариф, оплатите, получите доступ и подключитесь по инструкции.</p>",
            body=(
                "<p><strong>1.</strong> Оформляете доступ в личном кабинете.</p>"
                "<p><strong>2.</strong> После оплаты сразу получаете ссылку и QR-код.</p>"
                "<p><strong>3.</strong> Подключаетесь в приложении за 1-2 минуты.</p>"
            ),
            seo_title="Как работает VXcloud",
            search_description="Как работает VXcloud: оплата, получение доступа, подключение и продление.",
        )

        faq = self._ensure_page(
            parent=home,
            title="FAQ",
            slug="faq",
            show_in_menus=True,
            intro="<p>Ответы на частые вопросы о доступе, оплате и подключении.</p>",
            body=(
                "<p><strong>Когда доступ активируется?</strong> Обычно сразу после успешной оплаты.</p>"
                "<p><strong>Как продлить?</strong> В личном кабинете нажмите «Продлить».</p>"
                "<p><strong>Куда писать, если не работает?</strong> Через поддержку в боте или на сайте.</p>"
            ),
            seo_title="FAQ VXcloud",
            search_description="Частые вопросы VXcloud: подключение, оплата, продление и поддержка.",
        )

        help_page = self._ensure_page(
            parent=home,
            title="Инструкции",
            slug="help",
            show_in_menus=True,
            intro="<p>Пошаговые инструкции по установке приложения, оплате и подключению.</p>",
            body="<p>Откройте нужный раздел ниже.</p>",
            seo_title="Инструкции VXcloud",
            search_description="Пошаговые инструкции VXcloud для установки, оплаты и подключения.",
        )

        self._ensure_page(
            parent=help_page,
            title="Установка приложения",
            slug="install",
            show_in_menus=False,
            intro="<p>Пошаговая установка приложения для подключения.</p>",
            body=(
                "<p>1. Установите приложение из магазина приложений или по актуальной инструкции.</p>"
                "<p>2. Откройте ссылку доступа или импортируйте QR-код.</p>"
                "<p>3. Включите подключение.</p>"
            ),
        )
        self._ensure_page(
            parent=help_page,
            title="Оплата через Stars",
            slug="stars",
            show_in_menus=False,
            intro="<p>Как оплатить через Telegram Stars.</p>",
            body=(
                "<p>Оплата происходит внутри Telegram.</p>"
                "<p>После успешной оплаты доступ активируется автоматически.</p>"
            ),
        )
        self._ensure_page(
            parent=help_page,
            title="Подключение",
            slug="connect",
            show_in_menus=False,
            intro="<p>Подключение по ссылке или QR-коду.</p>",
            body=(
                "<p>Откройте доступ в личном кабинете.</p>"
                "<p>Выберите «Открыть», «QR-код» или «Скопировать».</p>"
            ),
        )

        legal_root = self._ensure_page(
            parent=home,
            title="Документы",
            slug="legal",
            show_in_menus=False,
            intro="<p>Юридические документы и обязательная информация для оплаты.</p>",
            body="<p>В этом разделе размещены оферта, политика и данные об услугах.</p>",
        )

        self._ensure_page(
            parent=legal_root,
            title="Условия использования",
            slug="terms",
            show_in_menus=False,
            intro="<p>Публичная оферта и условия предоставления цифрового доступа.</p>",
            body=(
                "<h2>1. Предмет</h2>"
                "<p>Сервис VXcloud предоставляет пользователю цифровой доступ к сети на оплаченный срок.</p>"
                "<h2>2. Порядок оказания услуги</h2>"
                "<p>Услуга считается оказанной после предоставления пользователю ссылки/QR-кода доступа.</p>"
                "<h2>3. Стоимость и оплата</h2>"
                "<p>Актуальная стоимость указывается на сайте в личном кабинете до оплаты.</p>"
                "<h2>4. Возвраты</h2>"
                "<p>Порядок возврата и рассмотрения обращений указывается в соответствии с действующим законодательством.</p>"
                "<h2>5. Поддержка</h2>"
                "<p>По всем вопросам пользователь может обратиться в поддержку через сайт или Telegram-бот.</p>"
            ),
            seo_title="Условия использования VXcloud",
            search_description="Публичная оферта и условия использования сервиса VXcloud.",
        )

        self._ensure_page(
            parent=legal_root,
            title="Политика конфиденциальности",
            slug="privacy",
            show_in_menus=False,
            intro="<p>Порядок обработки персональных данных пользователей VXcloud.</p>",
            body=(
                "<h2>1. Какие данные собираются</h2>"
                "<p>Для работы сервиса могут обрабатываться: Telegram ID, email, технические данные сессий и платежные статусы.</p>"
                "<h2>2. Цель обработки</h2>"
                "<p>Предоставление доступа, поддержка пользователей, выполнение обязательств по оплате и безопасности.</p>"
                "<h2>3. Передача данных</h2>"
                "<p>Данные передаются только необходимым платежным и техническим провайдерам в рамках оказания услуги.</p>"
                "<h2>4. Контакты по персональным данным</h2>"
                "<p>По вопросам персональных данных используйте контактные данные на странице «Контакты и реквизиты».</p>"
            ),
            seo_title="Политика конфиденциальности VXcloud",
            search_description="Политика обработки персональных данных сервиса VXcloud.",
        )

        self._ensure_page(
            parent=legal_root,
            title="Услуги и тарифы",
            slug="services",
            show_in_menus=False,
            intro="<p>Описание цифровых услуг VXcloud и действующих тарифов.</p>",
            body=(
                "<h2>Что продается</h2>"
                "<p>Цифровой доступ к VPN-сервису VXcloud на ограниченный срок.</p>"
                "<h2>Тариф</h2>"
                "<p>Базовый тариф: 30 дней доступа. Цена указывается перед оплатой в личном кабинете.</p>"
                "<h2>Что получает пользователь</h2>"
                "<ul>"
                "<li>Ссылку для подключения;</li>"
                "<li>QR-код для быстрого входа;</li>"
                "<li>Инструкцию по подключению;</li>"
                "<li>Поддержку при вопросах подключения.</li>"
                "</ul>"
            ),
            seo_title="Услуги и тарифы VXcloud",
            search_description="Описание услуг VXcloud, стоимость, состав цифрового доступа.",
        )

        self._ensure_page(
            parent=legal_root,
            title="Доставка и получение",
            slug="delivery",
            show_in_menus=False,
            intro="<p>Порядок получения цифрового доступа после оплаты.</p>",
            body=(
                "<p>VXcloud предоставляет цифровую услугу, физическая доставка отсутствует.</p>"
                "<p>После успешной оплаты пользователь получает доступ автоматически в личном кабинете и/или в Telegram-боте.</p>"
                "<p>Если активация не произошла автоматически, обратитесь в поддержку и укажите ID клиента.</p>"
            ),
            seo_title="Доставка и получение цифрового доступа VXcloud",
            search_description="Порядок выдачи цифрового доступа VXcloud после оплаты.",
        )

        self._ensure_page(
            parent=legal_root,
            title="Контакты и реквизиты",
            slug="contacts",
            show_in_menus=False,
            intro="<p>Контактная и юридическая информация владельца сервиса.</p>",
            body=(
                "<p><strong>Поддержка:</strong> @VXcloud_rubot</p>"
                "<p><strong>Email:</strong> support@vxcloud.ru</p>"
                "<p><strong>Сайт:</strong> https://vxcloud.ru</p>"
                "<hr />"
                "<p><strong>Владелец:</strong> заполните ФИО / название ИП или ООО</p>"
                "<p><strong>ИНН:</strong> заполните ИНН</p>"
                "<p><strong>ОГРНИП / ОГРН:</strong> заполните при необходимости</p>"
                "<p><strong>Юридический адрес:</strong> заполните адрес</p>"
                "<p><strong>Банковские реквизиты:</strong> банк, расчетный счет, БИК, кор. счет</p>"
                "<p>Перед отправкой сайта на проверку YooKassa замените заглушки на реальные данные.</p>"
            ),
            seo_title="Контакты и реквизиты VXcloud",
            search_description="Контактные данные и реквизиты сервиса VXcloud.",
        )

        self.stdout.write(self.style.SUCCESS("YooKassa-ready pages are created/updated in Wagtail."))
        self.stdout.write(self.style.SUCCESS(f"Check in admin: /cms-admin/pages/{home.id}/"))
        self.stdout.write(self.style.SUCCESS(f"Key pages: /how-it-works/, /faq/, /help/, /legal/terms/, /legal/privacy/"))

    def _ensure_site(self, root_page: Page, hostname: str, *, is_default: bool) -> None:
        site = Site.objects.filter(hostname=hostname).first()
        if site is None:
            site = Site(hostname=hostname)
        site.port = 80
        site.site_name = "VXcloud"
        site.root_page = root_page
        site.is_default_site = is_default
        site.save()

    def _ensure_page(
        self,
        *,
        parent: CMSHomePage | CMSContentPage,
        title: str,
        slug: str,
        show_in_menus: bool,
        intro: str,
        body: str,
        seo_title: str | None = None,
        search_description: str | None = None,
    ) -> CMSContentPage:
        child = parent.get_children().type(CMSContentPage).filter(slug=slug).first()
        if child:
            page = child.specific
            page.title = title
            page.slug = slug
            page.show_in_menus = show_in_menus
            page.intro = intro
            page.body = body
            if seo_title is not None:
                page.seo_title = seo_title
            if search_description is not None:
                page.search_description = search_description
            page.save()
            if not page.live:
                page.save_revision().publish()
            return page

        page = CMSContentPage(
            title=title,
            slug=slug,
            show_in_menus=show_in_menus,
            intro=intro,
            body=body,
            seo_title=seo_title or "",
            search_description=search_description or "",
        )
        parent.add_child(instance=page)
        page.save_revision().publish()
        return page

