import json
import os
import sys

sys.path.insert(0, "src")
sys.path.insert(0, ".")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "financial_bill.settings")
import django  # noqa: E402

django.setup()
from django.test import Client  # noqa: E402

c = Client()
s = c.get("/api/schema", HTTP_ACCEPT="application/json").json()
print(json.dumps(s["paths"]["/api/v1/channels"]["get"]["responses"], ensure_ascii=False)[:900])
print(json.dumps(s["paths"]["/api/v1/auth/logout"]["get"], ensure_ascii=False)[:400])
