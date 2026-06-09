from __future__ import annotations

import csv
import io

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.course import Course
from app.models.enrollment import EnrollmentStatus
from app.schemas.enrollment import EnrollmentCreate
from app.schemas.student import StudentCreate
from app.services.enrollment_service import create_enrollment
from app.services.student_service import create_student, get_student_by_email, normalize_student_email_domain


def import_students_csv(db: Session, content: bytes) -> dict[str, object]:
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    required = {"nome", "cognome", "email"}
    if not required.issubset(reader.fieldnames or []):
        raise ValueError("CSV iscritti non valido. Colonne richieste: nome,cognome,email.")
    created = 0
    skipped = 0
    errors: list[str] = []
    for line, row in enumerate(reader, start=2):
        try:
            raw_email = (row.get("email") or "").strip().lower()
            if not raw_email:
                raise ValueError("email mancante")
            email = normalize_student_email_domain(raw_email)
            if get_student_by_email(db, email):
                skipped += 1
                continue
            create_student(
                db,
                StudentCreate(
                    first_name=(row.get("nome") or "").strip(),
                    last_name=(row.get("cognome") or "").strip(),
                    email=email,
                    phone=(row.get("telefono") or "").strip(),
                    organization=(row.get("azienda_ente") or row.get("azienda") or "").strip(),
                    notes=(row.get("note") or "").strip(),
                ),
            )
            created += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Riga {line}: {exc}")
    return {"created": created, "skipped": skipped, "errors": errors}


def import_enrollments_csv(db: Session, content: bytes) -> dict[str, object]:
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if "email_iscritto" not in (reader.fieldnames or []):
        raise ValueError("CSV iscrizioni non valido. Colonna richiesta: email_iscritto.")
    created = 0
    skipped = 0
    errors: list[str] = []
    for line, row in enumerate(reader, start=2):
        try:
            student = get_student_by_email(db, (row.get("email_iscritto") or "").strip().lower())
            if not student:
                raise ValueError("iscritto non trovato")
            course = None
            if row.get("corso_id"):
                course = db.get(Course, int(row["corso_id"]))
            elif row.get("corso_titolo"):
                course = db.scalar(select(Course).where(Course.title == row["corso_titolo"].strip()))
            if not course:
                raise ValueError("corso non trovato")
            try:
                create_enrollment(
                    db,
                    EnrollmentCreate(
                        course_id=course.id,
                        student_id=student.id,
                        status=EnrollmentStatus(row.get("stato") or "non_completato"),
                        notes=(row.get("note") or "").strip(),
                    ),
                )
                created += 1
            except ValueError as exc:
                if "già iscritta" in str(exc):
                    skipped += 1
                else:
                    raise
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Riga {line}: {exc}")
    return {"created": created, "skipped": skipped, "errors": errors}

