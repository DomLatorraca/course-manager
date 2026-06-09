from __future__ import annotations

from dataclasses import dataclass
import re

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.enrollment import Enrollment
from app.models.student import Student
from app.schemas.student import StudentCreate, StudentUpdate


STUDENT_EMAIL_DOMAIN = "digitaltrainingacademy.it"


@dataclass(frozen=True)
class StudentEmailNormalizationResult:
    updated: int = 0
    unchanged: int = 0


def list_students(db: Session, q: str = "") -> list[Student]:
    stmt = select(Student).order_by(Student.last_name.asc(), Student.first_name.asc())
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(
            or_(
                Student.first_name.ilike(pattern),
                Student.last_name.ilike(pattern),
                Student.email.ilike(pattern),
                Student.organization.ilike(pattern),
            )
        )
    return list(db.scalars(stmt).all())


def get_student(db: Session, student_id: int) -> Student | None:
    return db.get(Student, student_id)


def get_student_by_email(db: Session, email: str) -> Student | None:
    return db.scalar(select(Student).where(Student.email == normalize_student_email_domain(email)))


def create_student(db: Session, data: StudentCreate) -> Student:
    email = normalize_student_email_domain(data.email)
    if get_student_by_email(db, email):
        raise ValueError("Email già presente in anagrafica.")
    values = data.model_dump()
    values["email"] = email
    student = Student(**values)
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


def update_student(db: Session, student: Student, data: StudentUpdate) -> Student:
    new_email = normalize_student_email_domain(data.email)
    existing = get_student_by_email(db, new_email)
    if existing and existing.id != student.id:
        raise ValueError("Email già presente in anagrafica.")
    values = data.model_dump()
    values["email"] = new_email
    for key, value in values.items():
        setattr(student, key, value)
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


def delete_student(db: Session, student: Student) -> None:
    count = db.scalar(select(func.count()).select_from(Enrollment).where(Enrollment.student_id == student.id))
    if count:
        raise ValueError("L'iscritto ha iscrizioni associate e non può essere eliminato.")
    db.delete(student)
    db.commit()


def normalize_student_email_domain(email: str) -> str:
    local_part = (email or "").strip().lower().split("@", 1)[0]
    local_part = _safe_email_local(local_part)
    return f"{local_part}@{STUDENT_EMAIL_DOMAIN}"


def normalize_all_student_email_domains(db: Session, dry_run: bool = False) -> StudentEmailNormalizationResult:
    updated = 0
    unchanged = 0
    reserved: set[str] = set()
    students = list(db.scalars(select(Student).order_by(Student.id)).all())
    changes: list[tuple[Student, str]] = []

    for student in students:
        normalized = _unique_email(normalize_student_email_domain(student.email), reserved)
        reserved.add(normalized)
        if student.email == normalized:
            unchanged += 1
            continue
        updated += 1
        changes.append((student, normalized))

    if dry_run:
        db.rollback()
    else:
        for student, _ in changes:
            student.email = f"tmp-email-{student.id}@{STUDENT_EMAIL_DOMAIN}"
            db.add(student)
        if changes:
            db.flush()
        for student, normalized in changes:
            student.email = normalized
            db.add(student)
        db.commit()

    return StudentEmailNormalizationResult(updated=updated, unchanged=unchanged)


def _safe_email_local(value: str) -> str:
    cleaned = re.sub(r"\s+", "-", value.strip().lower())
    cleaned = re.sub(r"[^a-z0-9._%+-]+", "-", cleaned)
    cleaned = re.sub(r"[._%+-]{2,}", "-", cleaned).strip("._%+-")
    return cleaned or "iscritto"


def _unique_email(email: str, reserved: set[str]) -> str:
    if email not in reserved:
        return email
    local_part, domain = email.split("@", 1)
    index = 2
    while True:
        candidate = f"{local_part}-{index}@{domain}"
        if candidate not in reserved:
            return candidate
        index += 1

