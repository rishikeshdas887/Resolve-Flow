"""Create a ResolveFlow user safely.

Usage:
  python scripts/create_user.py --email admin@example.com --role admin --password 'S3cure!' --name "Admin"

Password may also come from env var RESOLVEFLOW_PASSWORD to avoid shell history.
Never uses a default/predictable password — it must be supplied.
"""
import argparse
import getpass
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.models import Role, User
from app.db.session import make_session_factory


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    parser.add_argument("--role", choices=[r.value for r in Role], required=True)
    parser.add_argument("--name", default="")
    parser.add_argument("--password", default=None)
    args = parser.parse_args()

    password = args.password or os.environ.get("RESOLVEFLOW_PASSWORD")
    if not password:
        password = getpass.getpass("Password (min 8 chars): ")
    if len(password) < 8:
        print("Password must be at least 8 characters", file=sys.stderr)
        return 2

    settings = get_settings()
    session_factory = make_session_factory(settings.database_url)
    db = session_factory()
    try:
        existing = db.execute(select(User).where(User.email == args.email)).scalar_one_or_none()
        if existing:
            print(f"User {args.email} already exists (id={existing.id}); not modified.")
            return 0
        user = User(
            email=args.email,
            full_name=args.name or args.email.split("@")[0],
            password_hash=hash_password(password),
            role=Role(args.role),
        )
        db.add(user)
        db.commit()
        print(f"Created {args.role} user {args.email} (id={user.id})")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
