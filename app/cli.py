from __future__ import annotations

import argparse
import getpass
from pathlib import Path

from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal, init_db
from app.models.user import User, UserRole
from app.services.auth_service import change_password, create_user
from app.services.excel_import_service import import_excel_courses_to_db


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


def cmd_import_excel_courses(args: argparse.Namespace) -> None:
    init_db()
    path = Path(args.path).expanduser().resolve() if args.path else None
    sheet_name = args.sheet or None
    with SessionLocal() as db:
        result = import_excel_courses_to_db(
            db,
            path=path,
            sheet_name=sheet_name,
            update_existing=not args.no_update_existing,
            dry_run=args.dry_run,
        )

    mode = "simulazione" if args.dry_run else "import"
    print(
        f"Risultato {mode} corsi Excel: "
        f"creati={result.created}, aggiornati={result.updated}, saltati={result.skipped}."
    )
    if result.errors:
        print("Errori:")
        for error in result.errors:
            print(f"- {error}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Course Manager CLI")
    subparsers = parser.add_subparsers(required=True)

    init_parser = subparsers.add_parser("init-db", help="Crea le tabelle SQLite")
    init_parser.set_defaults(func=cmd_init_db)

    admin_parser = subparsers.add_parser("create-admin", help="Crea o aggiorna il primo admin")
    admin_parser.add_argument("--username")
    admin_parser.add_argument("--password")
    admin_parser.set_defaults(func=cmd_create_admin)

    import_excel_parser = subparsers.add_parser("import-excel-courses", help="Importa o aggiorna i corsi dal file Excel nel database")
    import_excel_parser.add_argument("--path", help="Percorso del workbook Excel. Se omesso usa EXCEL_COURSES_PATH.")
    import_excel_parser.add_argument("--sheet", help="Nome del foglio corsi. Se omesso usa EXCEL_COURSES_SHEET.")
    import_excel_parser.add_argument("--no-update-existing", action="store_true", help="Non aggiornare corsi già presenti con lo stesso titolo")
    import_excel_parser.add_argument("--dry-run", action="store_true", help="Mostra cosa verrebbe importato senza scrivere nel database")
    import_excel_parser.set_defaults(func=cmd_import_excel_courses)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

