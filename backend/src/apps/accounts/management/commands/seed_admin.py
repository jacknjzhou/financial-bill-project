from django.core.management.base import BaseCommand

from apps.accounts.models import User


class Command(BaseCommand):
    """初始化管理员账号（幂等：已存在则跳过并提示）。"""

    help = "创建初始 admin 账号（首登强制改密）"

    def add_arguments(self, parser):
        parser.add_argument("--username", default="admin")
        parser.add_argument("--password", default="Admin@123")

    def handle(self, *args, **options):
        username = options["username"]
        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING(f"账号 {username} 已存在，跳过"))
            return
        user = User.objects.create_user(
            username,
            password=options["password"],
            role=User.Role.ADMIN,
            is_staff=True,
            is_superuser=True,
        )
        user.must_change_password = True
        user.save(update_fields=["must_change_password"])
        self.stdout.write(
            self.style.SUCCESS(f"已创建管理员 {username}（must_change_password=True，首登强制改密）")
        )
