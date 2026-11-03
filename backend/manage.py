#!/usr/bin/env python
import os
import sys
from pathlib import Path


def main() -> None:
    # 标准 src layout：把 src/ 加入 sys.path
    sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "financial_bill.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Cannot import Django. Did you run pip install -r requirements.txt?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
