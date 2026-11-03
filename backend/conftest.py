"""pytest 入口：把 src/ 加入 sys.path（标准 src layout）。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
# 注：测试环境变量（OIDC_ENABLED=1）由 pytest_env 插件在更早阶段固定（见 pytest.ini）。
