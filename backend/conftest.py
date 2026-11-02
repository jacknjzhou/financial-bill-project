"""pytest 入口：把 src/ 加入 sys.path（标准 src layout）。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
