"""pytest 早加载插件（pytest.ini 的 `-p pytest_env`，在任何 conftest/Django setup 之前）。

测试环境固定 OIDC 开启（T2B 全链路 SSO 测试需要）；生产开关由 .env 决定。
"""
import os

os.environ["OIDC_ENABLED"] = "1"
