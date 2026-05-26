from __future__ import annotations

import argparse
import getpass

from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal, init_db
from app.models.user import User, UserRole
from app.services.auth_service import change_password, create_user


def cmd_init_db(_: argparse.Namespace) -> None:
    init_db()
    print("Database inizializzato.")


def cmd_create_admin(args: argparse.Namespace) -> None:
    init_db()
    settings = get_settings()
    username = args.username or settings.admin_default_username
    password = args.password or settings.admin_default_password
    if not password or password == "change-me-on-first-login":
        password = getpass.getpass("Password admin: ")
    with SessionLocal() as db:
        existing = db.scalar(select(User).where(User.username == username))
        if existing:
            if existing.role != UserRole.admin:
                existing.role = UserRole.admin
            change_password(db, existing, password)
            print(f"Admin esistente aggiornato: {username}")
            return
        create_user(db, username, password, UserRole.admin)
        print(f"Admin creato: {username}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Course Manager CLI")
    subparsers = parser.add_subparsers(required=True)

    init_parser = subparsers.add_parser("init-db", help="Crea le tabelle SQLite")
    init_parser.set_defaults(func=cmd_init_db)

    admin_parser = subparsers.add_parser("create-admin", help="Crea o aggiorna il primo admin")
    admin_parser.add_argument("--username")
    admin_parser.add_argument("--password")
    admin_parser.set_defaults(func=cmd_create_admin)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

