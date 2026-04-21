from __future__ import annotations

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from blog.models import Category, Page, Post, PostType, SiteText
from cabinet.models import BotUser, EdgeServer, VPNNode


class StaffAuthenticationForm(AuthenticationForm):
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_staff:
            raise ValidationError("Доступ в админ-панель только для staff-пользователей.", code="not_staff")


class BootstrapFormMixin:
    def _apply_bootstrap_classes(self):
        for name, field in self.fields.items():
            widget = field.widget
            classes = widget.attrs.get("class", "")
            base = classes.split()

            if isinstance(widget, forms.CheckboxInput):
                target = "form-check-input"
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                target = "form-select"
            else:
                target = "form-control"

            if target not in base:
                base.append(target)
            widget.attrs["class"] = " ".join(c for c in base if c)

            if name == "content_blocks":
                widget.attrs["class"] += " js-block-editor-source"
                widget.attrs.setdefault("rows", 6)
            if name == "content":
                widget.attrs.setdefault("rows", 14)

            if isinstance(widget, forms.DateTimeInput):
                widget.input_type = "datetime-local"


def _bot_user_display_name(user: BotUser) -> str:
    first_name = str(getattr(user, "first_name", "") or "").strip()
    username = str(getattr(user, "username", "") or "").strip()
    client_code = str(getattr(user, "client_code", "") or "").strip()
    primary = first_name or username or client_code or f"User #{int(user.id)}"
    details: list[str] = [f"ID {int(user.id)}"]
    if username and username != primary:
        details.append(f"@{username}")
    if client_code and client_code != primary:
        details.append(client_code)
    return f"{primary} ({', '.join(details)})"


class BotUserChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj: BotUser) -> str:
        return _bot_user_display_name(obj)


class BackofficePostForm(BootstrapFormMixin, forms.ModelForm):
    published_at = forms.DateTimeField(
        required=False,
        input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"],
        widget=forms.DateTimeInput(format="%Y-%m-%dT%H:%M"),
        label="Дата публикации",
    )

    class Meta:
        model = Post
        fields = [
            "title",
            "slug",
            "summary",
            "post_type",
            "categories",
            "is_published",
            "published_at",
            "content_blocks",
            "content",
        ]
        widgets = {
            "summary": forms.Textarea(attrs={"rows": 3}),
            "content_blocks": forms.Textarea(attrs={"rows": 6}),
            "content": forms.Textarea(attrs={"rows": 14}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["categories"].queryset = Category.objects.order_by("title")
        self.fields["post_type"].queryset = PostType.objects.order_by("title")
        self.fields["title"].label = "Заголовок"
        self.fields["slug"].label = "Slug"
        self.fields["summary"].label = "Краткое описание"
        self.fields["post_type"].label = "Тип поста"
        self.fields["categories"].label = "Категории"
        self.fields["is_published"].label = "Опубликован"
        self.fields["content_blocks"].label = "Контент (блоки)"
        self.fields["content"].label = "HTML fallback"
        self.fields["content_blocks"].help_text = "Gutenberg-подобный редактор блоков."
        self.fields["content"].help_text = "Резервное поле HTML, если блоки не используются."
        self._apply_bootstrap_classes()


class BackofficePageForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Page
        fields = [
            "title",
            "slug",
            "path",
            "summary",
            "is_published",
            "is_homepage",
            "show_in_nav",
            "nav_title",
            "nav_order",
            "posts_enabled",
            "posts_title",
            "posts_source",
            "posts_limit",
            "post_types",
            "post_categories",
            "manual_posts",
            "content_blocks",
            "content",
        ]
        widgets = {
            "summary": forms.Textarea(attrs={"rows": 3}),
            "content_blocks": forms.Textarea(attrs={"rows": 6}),
            "content": forms.Textarea(attrs={"rows": 14}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["post_types"].queryset = PostType.objects.order_by("title")
        self.fields["post_categories"].queryset = Category.objects.order_by("title")
        self.fields["manual_posts"].queryset = Post.objects.order_by("-published_at", "-id")
        self.fields["title"].label = "Заголовок"
        self.fields["slug"].label = "Slug"
        self.fields["path"].label = "Путь URL"
        self.fields["summary"].label = "Краткое описание"
        self.fields["is_published"].label = "Опубликована"
        self.fields["is_homepage"].label = "Главная страница"
        self.fields["show_in_nav"].label = "Показывать в меню"
        self.fields["nav_title"].label = "Название в меню"
        self.fields["nav_order"].label = "Порядок в меню"
        self.fields["posts_enabled"].label = "Показывать ленту постов"
        self.fields["posts_title"].label = "Заголовок ленты"
        self.fields["posts_source"].label = "Источник постов"
        self.fields["posts_limit"].label = "Лимит постов"
        self.fields["post_types"].label = "Типы постов"
        self.fields["post_categories"].label = "Категории постов"
        self.fields["manual_posts"].label = "Выбранные посты"
        self.fields["content_blocks"].label = "Контент (блоки)"
        self.fields["content"].label = "HTML fallback"
        self.fields["path"].help_text = "Например: /instructions/ или /help/ios/"
        self.fields["content_blocks"].help_text = "Gutenberg-подобный редактор блоков."
        self.fields["content"].help_text = "Резервное поле HTML, если блоки не используются."
        self._apply_bootstrap_classes()


class BackofficeCategoryForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Category
        fields = ["title", "slug", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["title"].label = "Название"
        self.fields["slug"].label = "Slug"
        self.fields["is_active"].label = "Активна"
        self._apply_bootstrap_classes()


class BackofficePostTypeForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = PostType
        fields = ["title", "slug", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["title"].label = "Название"
        self.fields["slug"].label = "Slug"
        self.fields["is_active"].label = "Активен"
        self._apply_bootstrap_classes()


class BackofficeSiteTextForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = SiteText
        fields = ["key", "value"]
        widgets = {"value": forms.Textarea(attrs={"rows": 6})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["key"].label = "Ключ"
        self.fields["value"].label = "Значение"
        self._apply_bootstrap_classes()


class TicketReplyForm(BootstrapFormMixin, forms.Form):
    message = forms.CharField(
        label="Ответ пользователю",
        widget=forms.Textarea(attrs={"rows": 5, "placeholder": "Напишите ответ от имени поддержки"}),
    )
    close_after_send = forms.BooleanField(
        required=False,
        initial=False,
        label="Закрыть тикет после отправки",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap_classes()


class BackofficeUserCreateForm(BootstrapFormMixin, forms.Form):
    username = forms.CharField(
        label="Логин",
        max_length=150,
        help_text="Используется для входа на сайт. Проверяется без учёта регистра.",
    )
    first_name = forms.CharField(
        label="Имя",
        max_length=150,
        required=False,
        help_text="Человеческое имя для /ops и списка подписок.",
    )
    email = forms.EmailField(
        label="Email",
        required=False,
        help_text="Необязательно. Нужен только если хотите хранить email в аккаунте сайта.",
    )
    password = forms.CharField(
        label="Пароль",
        required=False,
        widget=forms.PasswordInput(render_value=True),
        help_text="Оставьте пустым, чтобы сгенерировать пароль автоматически.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap_classes()

    def clean_username(self):
        username = (self.cleaned_data.get("username") or "").strip()
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("Пользователь с таким логином уже существует")
        return username

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if email and User.objects.filter(email__iexact=email).exists():
            raise ValidationError("Пользователь с таким email уже существует")
        return email

    def clean_first_name(self):
        return (self.cleaned_data.get("first_name") or "").strip()


class BackofficeUserPasswordResetForm(BootstrapFormMixin, forms.Form):
    password = forms.CharField(
        label="Новый пароль",
        required=False,
        widget=forms.PasswordInput(render_value=True),
        help_text="Оставьте пустым, чтобы сгенерировать пароль автоматически.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap_classes()


class BackofficeSubscriptionExpiryForm(BootstrapFormMixin, forms.Form):
    user_id = forms.IntegerField(
        label="User ID",
        min_value=1,
        required=False,
        help_text="ID пользователя из /ops -> Пользователи. Если оставить пустым, останется текущий.",
    )
    display_name = forms.CharField(
        label="Имя подписки",
        max_length=255,
        required=False,
        help_text="Понятное имя для списка подписок и comment в 3x-ui.",
    )
    expires_at = forms.DateTimeField(
        label="Дата окончания",
        required=False,
        input_formats=[
            "%d/%m/%Y %H:%M",
            "%d.%m.%Y %H:%M",
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%m/%d/%Y %I:%M %p",
            "%m/%d/%Y %I:%M:%S %p",
        ],
        widget=forms.TextInput(
            attrs={
                "placeholder": "дд/мм/гггг чч:мм",
                "autocomplete": "off",
            }
        ),
        help_text="Оставьте пустым для бессрочной подписки. Формат: дд/мм/гггг чч:мм.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap_classes()

    def clean_user_id(self) -> int | None:
        user_id = self.cleaned_data.get("user_id")
        if user_id in (None, ""):
            return None
        user_id = int(user_id)
        if not BotUser.objects.filter(pk=user_id).exists():
            raise ValidationError("Пользователь не найден.")
        return user_id


class BackofficeSubscriptionCreateForm(BootstrapFormMixin, forms.Form):
    user_id = BotUserChoiceField(
        label="Пользователь",
        queryset=BotUser.objects.none(),
        empty_label=None,
        help_text="Начните вводить имя и выберите пользователя из выпадающего списка.",
    )
    display_name = forms.CharField(
        label="Имя подписки",
        max_length=255,
        help_text="Понятное имя для списка подписок в /ops и в кабинете.",
    )
    expires_at = forms.DateTimeField(
        label="Дата окончания",
        required=False,
        input_formats=[
            "%d/%m/%Y %H:%M",
            "%d.%m.%Y %H:%M",
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%m/%d/%Y %I:%M %p",
            "%m/%d/%Y %I:%M:%S %p",
        ],
        widget=forms.TextInput(
            attrs={
                "placeholder": "дд/мм/гггг чч:мм",
                "autocomplete": "off",
            }
        ),
        help_text="Оставьте пустым для бессрочной подписки. Формат: дд/мм/гггг чч:мм.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["user_id"].queryset = BotUser.objects.order_by("first_name", "username", "id")
        self._apply_bootstrap_classes()

    def clean_user_id(self) -> BotUser:
        user = self.cleaned_data["user_id"]
        if user is None:
            raise ValidationError("Пользователь не найден.")
        return user


class BackofficeVPNNodeForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = VPNNode
        fields = [
            "name",
            "region",
            "xui_base_url",
            "xui_username",
            "xui_password",
            "xui_inbound_id",
            "public_ip",
            "node_fqdn",
            "compatibility_pool",
            "xray_api_host",
            "xray_api_port",
            "xray_metrics_host",
            "xray_metrics_port",
            "bandwidth_capacity_mbps",
            "connection_capacity",
            "backend_host",
            "backend_port",
            "backend_weight",
            "is_active",
            "lb_enabled",
            "needs_backfill",
        ]
        widgets = {
            "xui_password": forms.PasswordInput(render_value=True),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].label = "Имя ноды"
        self.fields["region"].label = "Регион"
        self.fields["xui_base_url"].label = "3x-ui URL"
        self.fields["xui_username"].label = "3x-ui логин"
        self.fields["xui_password"].label = "3x-ui пароль"
        self.fields["xui_inbound_id"].label = "3x-ui inbound ID"
        self.fields["public_ip"].label = "Public IP"
        self.fields["node_fqdn"].label = "Node FQDN"
        self.fields["compatibility_pool"].label = "Compatibility pool"
        self.fields["xray_api_host"].label = "Xray API host"
        self.fields["xray_api_port"].label = "Xray API port"
        self.fields["xray_metrics_host"].label = "Xray metrics host"
        self.fields["xray_metrics_port"].label = "Xray metrics port"
        self.fields["bandwidth_capacity_mbps"].label = "Bandwidth capacity (Mbps)"
        self.fields["connection_capacity"].label = "Connection capacity"
        self.fields["backend_host"].label = "Backend host"
        self.fields["backend_port"].label = "Backend port"
        self.fields["backend_weight"].label = "Вес в HAProxy"
        self.fields["is_active"].label = "Нода активна"
        self.fields["lb_enabled"].label = "Включить в load balancer"
        self.fields["needs_backfill"].label = "Требует backfill"

        self.fields["xui_base_url"].help_text = "Например: https://node-1.example.com:2053"
        self.fields["public_ip"].help_text = "Публичный IPv4 ноды, на который будут указывать DNS alias cutover-ы."
        self.fields["node_fqdn"].help_text = "Стабильное имя самой ноды, если хотите хранить его отдельно от alias."
        self.fields["compatibility_pool"].help_text = "Только ноды из одного pool могут обмениваться подписками через DNS rebalance."
        self.fields["xray_api_host"].help_text = "Loopback/внутренний host Xray API для будущей stats automation."
        self.fields["xray_metrics_host"].help_text = "Loopback/внутренний host Xray metrics listener."
        self.fields["backend_host"].help_text = "Куда HAProxy будет направлять VPN-трафик."
        self.fields["backend_port"].help_text = "Обычно тот же inbound port Xray на ноде."
        self.fields["lb_enabled"].help_text = "Новые подключения пойдут на ноду только если это поле включено, health=ok и backfill завершён."
        self.fields["needs_backfill"].help_text = "Оставьте включённым для новой ноды, пока не закончите sync и ручную проверку."

        self._apply_bootstrap_classes()


class BackofficeEdgeServerForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = EdgeServer
        fields = [
            "name",
            "public_host",
            "public_ip",
            "frontend_port",
            "healthcheck_host",
            "healthcheck_port",
            "is_active",
            "is_primary",
            "accept_new_clients",
            "priority",
            "notes",
        ]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].label = "Имя edge"
        self.fields["public_host"].label = "Публичный host"
        self.fields["public_ip"].label = "Публичный IP"
        self.fields["frontend_port"].label = "Frontend port"
        self.fields["healthcheck_host"].label = "Healthcheck host"
        self.fields["healthcheck_port"].label = "Healthcheck port"
        self.fields["is_active"].label = "Edge активен"
        self.fields["is_primary"].label = "Primary edge"
        self.fields["accept_new_clients"].label = "Принимать новых клиентов"
        self.fields["priority"].label = "Приоритет"
        self.fields["notes"].label = "Заметки"

        self.fields["public_host"].help_text = "Домен, на который указывает публичный VPN endpoint, например connect.vxcloud.ru."
        self.fields["public_ip"].help_text = "Публичный IP edge-сервера, который будет целевым DNS target."
        self.fields["frontend_port"].help_text = "Обычно 443 для отдельного VPN edge."
        self.fields["healthcheck_host"].help_text = "Если пусто, для healthcheck будет использоваться public_ip."
        self.fields["healthcheck_port"].help_text = "Если пусто, будет использоваться frontend_port."
        self.fields["is_primary"].help_text = "Primary edge — рекомендуемая текущая цель для DNS cutover."
        self.fields["accept_new_clients"].help_text = "Drain режим: если выключено, edge остаётся в inventory, но не считается подходящим для новых клиентов."
        self.fields["priority"].help_text = "Меньше число = выше приоритет при auto-selection primary edge."

        self._apply_bootstrap_classes()

    def clean_public_host(self) -> str:
        return str(self.cleaned_data.get("public_host") or "").strip().lower()

    def clean_public_ip(self) -> str:
        return str(self.cleaned_data.get("public_ip") or "").strip()

    def clean_healthcheck_host(self) -> str:
        return str(self.cleaned_data.get("healthcheck_host") or "").strip()

    def clean(self):
        cleaned = super().clean()
        is_active = bool(cleaned.get("is_active"))
        is_primary = bool(cleaned.get("is_primary"))
        accept_new_clients = bool(cleaned.get("accept_new_clients"))
        frontend_port = cleaned.get("frontend_port")
        healthcheck_port = cleaned.get("healthcheck_port")

        if is_primary and not is_active:
            self.add_error("is_primary", "Primary edge должен быть активным.")
        if accept_new_clients and not is_active:
            self.add_error("accept_new_clients", "Нельзя принимать новых клиентов на неактивном edge.")
        if frontend_port is not None and int(frontend_port) <= 0:
            self.add_error("frontend_port", "Порт должен быть больше нуля.")
        if healthcheck_port is not None and int(healthcheck_port) <= 0:
            self.add_error("healthcheck_port", "Порт healthcheck должен быть больше нуля.")
        return cleaned
