from django.apps import AppConfig


class MetaConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.meta"
    verbose_name = "基础配置"
