from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.enrollment import Enrollment
from app.models.student import Student
from app.schemas.student import StudentCreate, StudentUpdate


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
    return db.scalar(select(Student).where(Student.email == email.lower().strip()))


def create_student(db: Session, data: StudentCreate) -> Student:
    if get_student_by_email(db, data.email):
        raise ValueError("Email già presente in anagrafica.")
    values = data.model_dump()
    values["email"] = values["email"].lower().strip()
    student = Student(**values)
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


def update_student(db: Session, student: Student, data: StudentUpdate) -> Student:
    new_email = data.email.lower().strip()
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

