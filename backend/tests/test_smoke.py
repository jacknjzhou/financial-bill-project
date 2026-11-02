"""T1 冒烟：/api/health 可达且数据库连接正常。"""
from django.test import Client


class HealthTest:
    def test_health_ok(self, db):
        r = Client().get("/api/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok", "db": True}
