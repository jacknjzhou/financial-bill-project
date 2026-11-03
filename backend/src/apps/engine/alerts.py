"""告警：站内 Alert + 邮件（EMAIL_BACKEND 默认 console）。"""
from __future__ import annotations

import logging

from django.conf import settings as dj_settings
from django.core.mail import send_mail

from apps.engine.models import Alert

logger = logging.getLogger(__name__)


def send_alert(project, reconcile_date, kind: str, message: str) -> None:
    Alert.objects.create(project=project, reconcile_date=reconcile_date, kind=kind, message=message)
    kind_label = {"failed": "对账失败", "dispute": "新差异"}.get(kind, kind)
    subject = f"[对账告警] {project.name} {reconcile_date} {kind_label}"
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=dj_settings.EMAIL_FROM,
            recipient_list=list(dj_settings.ALERT_EMAIL_TO),
            fail_silently=True,
        )
    except Exception:  # noqa: BLE001 —— 邮件失败不影响主流程
        logger.warning("alert mail failed: %s", subject, exc_info=True)
