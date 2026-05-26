from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.course import Course
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.student import Student
from app.schemas.enrollment import EnrollmentCreate, EnrollmentUpdate


def list_enrollments(db: Session, course_id: int | None = None, student_id: int | None = None, status: str = "") -> list[Enrollment]:
    stmt = select(Enrollment).order_by(Enrollment.updated_at.desc())
    if course_id:
        stmt = stmt.where(Enrollment.course_id == course_id)
    if student_id:
        stmt = stmt.where(Enrollment.student_id == student_id)
    if status:
        try:
            stmt = stmt.where(Enrollment.status == EnrollmentStatus(status))
        except ValueError:
            return []
    return list(db.scalars(stmt).all())


def get_enrollment(db: Session, enrollment_id: int) -> Enrollment | None:
    return db.get(Enrollment, enrollment_id)


def create_enrollment(db: Session, data: EnrollmentCreate) -> Enrollment:
    if not db.get(Course, data.course_id):
        raise ValueError("Corso non trovato.")
    if not db.get(Student, data.student_id):
        raise ValueError("Iscritto non trovato.")
    existing = db.scalar(
        select(Enrollment).where(
            Enrollment.course_id == data.course_id,
            Enrollment.student_id == data.student_id,
        )
    )
    if existing:
        raise ValueError("La persona è già iscritta a questo corso.")
    enrollment = Enrollment(**data.model_dump())
    apply_completion_date(enrollment)
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)
    return enrollment


def apply_completion_date(enrollment: Enrollment) -> None:
    if enrollment.status == EnrollmentStatus.completato and enrollment.completed_at is None:
        enrollment.completed_at = datetime.utcnow()
    if enrollment.status == EnrollmentStatus.non_completato:
        enrollment.completed_at = None


def update_enrollment(db: Session, enrollment: Enrollment, data: EnrollmentUpdate) -> Enrollment:
    enrollment.status = data.status
    enrollment.notes = data.notes
    apply_completion_date(enrollment)
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)
    return enrollment


def delete_enrollment(db: Session, enrollment: Enrollment) -> None:
    db.delete(enrollment)
    db.commit()
