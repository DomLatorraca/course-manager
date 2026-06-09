from __future__ import annotations

import argparse
import getpass
from pathlib import Path

from sqlalchemy import delete, func, select

from app.config import get_settings
from app.database import SessionLocal, init_db
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.material import Material
from app.models.student import Student
from app.models.user import User, UserRole
from app.services.auth_service import change_password, create_user
from app.services.excel_import_service import import_excel_courses_to_db
from app.services.file_service import get_material_path
from app.services.material_package_service import import_material_package
from app.services.storage_material_import_service import import_storage_materials
from app.services.student_service import STUDENT_EMAIL_DOMAIN, normalize_all_student_email_domains
from app.services.teaching_material_service import generate_teaching_materials


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
            include_participants=not args.only_courses,
        )

    mode = "simulazione" if args.dry_run else "import"
    print(
        f"Risultato {mode} corsi Excel: "
        f"creati={result.created}, aggiornati={result.updated}, saltati={result.skipped}."
    )
    if not args.only_courses:
        print(
            "Iscritti/iscrizioni: "
            f"iscritti_creati={result.students_created}, "
            f"iscritti_aggiornati={result.students_updated}, "
            f"iscrizioni_create={result.enrollments_created}, "
            f"iscrizioni_aggiornate={result.enrollments_updated}, "
            f"iscrizioni_saltate={result.enrollments_skipped}."
        )
    if result.errors:
        print("Errori:")
        for error in result.errors:
            print(f"- {error}")


def cmd_generate_course_materials(args: argparse.Namespace) -> None:
    init_db()
    with SessionLocal() as db:
        result = generate_teaching_materials(
            db,
            course_id=args.course_id,
            overwrite=not args.no_overwrite,
            dry_run=args.dry_run,
        )

    mode = "simulazione" if args.dry_run else "generazione"
    print(
        f"Risultato {mode} materiali: "
        f"generati={result.generated}, aggiornati={result.updated}, saltati={result.skipped}."
    )
    if result.errors:
        print("Errori:")
        for error in result.errors:
            print(f"- {error}")


def cmd_import_material_package(args: argparse.Namespace) -> None:
    init_db()
    zip_path = Path(args.zip).expanduser().resolve()
    with SessionLocal() as db:
        result = import_material_package(
            db,
            zip_path=zip_path,
            overwrite=not args.no_overwrite,
            include_archives=args.include_archives,
            dry_run=args.dry_run,
        )

    mode = "simulazione" if args.dry_run else "import"
    print(
        f"Risultato {mode} pacchetto materiali: "
        f"creati={result.created}, aggiornati={result.updated}, saltati={result.skipped}."
    )
    if result.errors:
        print("Avvisi:")
        for error in result.errors:
            print(f"- {error}")


def cmd_import_storage_materials(args: argparse.Namespace) -> None:
    init_db()
    root_path = Path(args.path).expanduser().resolve() if args.path else None
    with SessionLocal() as db:
        result = import_storage_materials(
            db,
            root_path=root_path,
            overwrite=not args.no_overwrite,
            dry_run=args.dry_run,
        )

    mode = "simulazione" if args.dry_run else "import"
    print(
        f"Risultato {mode} materiali storage: "
        f"creati={result.created}, aggiornati={result.updated}, saltati={result.skipped}."
    )
    if result.errors:
        print("Avvisi:")
        for error in result.errors:
            print(f"- {error}")


def cmd_normalize_student_emails(args: argparse.Namespace) -> None:
    init_db()
    with SessionLocal() as db:
        result = normalize_all_student_email_domains(db, dry_run=args.dry_run)

    mode = "simulazione" if args.dry_run else "correzione"
    print(
        f"Risultato {mode} email iscritti: "
        f"aggiornate={result.updated}, già_corrette={result.unchanged}, dominio=@{STUDENT_EMAIL_DOMAIN}."
    )


def cmd_clear_training_data(args: argparse.Namespace) -> None:
    init_db()
    if not args.yes and not args.dry_run:
        raise SystemExit("Operazione annullata: aggiungi --yes per confermare la pulizia dei dati didattici.")

    with SessionLocal() as db:
        counts = {
            "materiali": db.scalar(select(func.count()).select_from(Material)) or 0,
            "iscrizioni": db.scalar(select(func.count()).select_from(Enrollment)) or 0,
            "iscritti": db.scalar(select(func.count()).select_from(Student)) or 0,
            "corsi": db.scalar(select(func.count()).select_from(Course)) or 0,
        }
        if args.dry_run:
            db.rollback()
        else:
            db.execute(delete(Material))
            db.execute(delete(Enrollment))
            db.execute(delete(Student))
            db.execute(delete(Course))
            db.commit()

    mode = "simulazione" if args.dry_run else "pulizia"
    print(
        f"Risultato {mode} dati didattici: "
        f"materiali={counts['materiali']}, "
        f"iscrizioni={counts['iscrizioni']}, "
        f"iscritti={counts['iscritti']}, "
        f"corsi={counts['corsi']}."
    )


def cmd_clear_course_materials(args: argparse.Namespace) -> None:
    init_db()
    if not args.yes and not args.dry_run:
        raise SystemExit("Operazione annullata: aggiungi --yes per confermare la pulizia dei materiali.")

    with SessionLocal() as db:
        materials = list(db.scalars(select(Material).order_by(Material.id)).all())
        files_to_delete: list[Path] = []
        invalid_paths: list[str] = []

        for material in materials:
            try:
                path = get_material_path(material)
            except ValueError as exc:
                invalid_paths.append(f"{material.id}: {exc}")
                continue
            if path.exists():
                files_to_delete.append(path)

        if args.dry_run:
            db.rollback()
        else:
            if not args.keep_files:
                for path in files_to_delete:
                    path.unlink(missing_ok=True)
            db.execute(delete(Material))
            db.commit()

    mode = "simulazione" if args.dry_run else "pulizia"
    print(
        f"Risultato {mode} materiali corsi: "
        f"materiali={len(materials)}, file_presenti={len(files_to_delete)}, percorsi_non_validi={len(invalid_paths)}."
    )
    if invalid_paths:
        print("Avvisi:")
        for warning in invalid_paths:
            print(f"- {warning}")


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
    import_excel_parser.add_argument("--only-courses", action="store_true", help="Importa solo l'anagrafica corsi, senza iscritti e iscrizioni")
    import_excel_parser.add_argument("--dry-run", action="store_true", help="Mostra cosa verrebbe importato senza scrivere nel database")
    import_excel_parser.set_defaults(func=cmd_import_excel_courses)

    materials_parser = subparsers.add_parser("generate-course-materials", help="Genera PDF didattici per i corsi e li registra nei materiali")
    materials_parser.add_argument("--course-id", type=int, help="Genera materiale solo per un corso specifico")
    materials_parser.add_argument("--no-overwrite", action="store_true", help="Non aggiornare materiali generati già esistenti")
    materials_parser.add_argument("--dry-run", action="store_true", help="Mostra cosa verrebbe generato senza scrivere file o database")
    materials_parser.set_defaults(func=cmd_generate_course_materials)

    import_materials_parser = subparsers.add_parser("import-material-package", help="Importa nello storage i materiali contenuti in un pacchetto zip")
    import_materials_parser.add_argument("--zip", required=True, help="Percorso del pacchetto zip materiali")
    import_materials_parser.add_argument("--no-overwrite", action="store_true", help="Non aggiornare materiali già importati")
    import_materials_parser.add_argument("--include-archives", action="store_true", help="Importa anche gli zip dei singoli corsi come file scaricabili")
    import_materials_parser.add_argument("--dry-run", action="store_true", help="Mostra cosa verrebbe importato senza scrivere file o database")
    import_materials_parser.set_defaults(func=cmd_import_material_package)

    import_storage_parser = subparsers.add_parser("import-storage-materials", help="Registra nel database file già presenti nello storage")
    import_storage_parser.add_argument("--path", help="Percorso da scansionare. Se omesso usa COURSE_FILES_DIR.")
    import_storage_parser.add_argument("--no-overwrite", action="store_true", help="Non aggiornare materiali già registrati")
    import_storage_parser.add_argument("--dry-run", action="store_true", help="Mostra cosa verrebbe importato senza scrivere database")
    import_storage_parser.set_defaults(func=cmd_import_storage_materials)

    normalize_emails_parser = subparsers.add_parser("normalize-student-emails", help="Corregge le email degli iscritti con il dominio digitaltrainingacademy.it")
    normalize_emails_parser.add_argument("--dry-run", action="store_true", help="Mostra quante email verrebbero corrette senza scrivere database")
    normalize_emails_parser.set_defaults(func=cmd_normalize_student_emails)

    clear_training_parser = subparsers.add_parser("clear-training-data", help="Svuota corsi, iscritti, iscrizioni e materiali dal database senza toccare gli utenti")
    clear_training_parser.add_argument("--yes", action="store_true", help="Conferma la pulizia dei dati didattici")
    clear_training_parser.add_argument("--dry-run", action="store_true", help="Mostra quanti dati verrebbero cancellati senza scrivere database")
    clear_training_parser.set_defaults(func=cmd_clear_training_data)

    clear_materials_parser = subparsers.add_parser("clear-course-materials", help="Rimuove dal database i materiali dei corsi senza toccare corsi, iscritti e utenti")
    clear_materials_parser.add_argument("--yes", action="store_true", help="Conferma la pulizia dei materiali")
    clear_materials_parser.add_argument("--keep-files", action="store_true", help="Cancella solo i record dal database, lasciando i file nello storage")
    clear_materials_parser.add_argument("--dry-run", action="store_true", help="Mostra quanti materiali verrebbero cancellati senza scrivere database")
    clear_materials_parser.set_defaults(func=cmd_clear_course_materials)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

