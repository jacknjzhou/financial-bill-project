import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "financial_bill.settings")

app = Celery("financial_bill")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
