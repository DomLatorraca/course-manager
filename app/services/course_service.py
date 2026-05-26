from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.course import Course, CourseStatus
from app.models.enrollment import Enrollment
from app.schemas.course import CourseCreate, CourseUpdate


def list_courses(db: Session, q: str = "", category: str = "", status: str = "") -> list[Course]:
    stmt = select(Course).order_by(Course.created_at.desc())
    if q:
        stmt = stmt.where(Course.title.ilike(f"%{q}%"))
    if category:
        stmt = stmt.where(Course.category.ilike(f"%{category}%"))
    if status:
        try:
            stmt = stmt.where(Course.status == CourseStatus(status))
        except ValueError:
            return []
    return list(db.scalars(stmt).all())


def get_course(db: Session, course_id: int) -> Course | None:
    return db.get(Course, course_id)


def create_course(db: Session, data: CourseCreate) -> Course:
    course = Course(**data.model_dump())
    db.add(course)
    db.commit()
    db.refresh(course)
    return course


def update_course(db: Session, course: Course, data: CourseUpdate) -> Course:
    for key, value in data.model_dump().items():
        setattr(course, key, value)
    db.add(course)
    db.commit()
    db.refresh(course)
    return course


def archive_course(db: Session, course: Course) -> Course:
    course.status = CourseStatus.archiviato
    db.add(course)
    db.commit()
    db.refresh(course)
    return course


def delete_course(db: Session, course: Course) -> None:
    count = db.scalar(select(func.count()).select_from(Enrollment).where(Enrollment.course_id == course.id))
    if count:
        raise ValueError("Il corso ha iscrizioni associate e non può essere eliminato. Archiviarlo invece.")
    db.delete(course)
    db.commit()
