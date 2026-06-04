from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.course import Course, CourseStatus
from app.services.excel_course_service import list_excel_courses


@dataclass(frozen=True)
class ExcelCourseImportResult:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


def import_excel_courses_to_db(
    db: Session,
    path: Path | None = None,
    sheet_name: str | None = None,
    update_existing: bool = True,
    dry_run: bool = False,
) -> ExcelCourseImportResult:
    created = 0
    updated = 0
    skipped = 0
    errors: list[str] = []

    excel_courses = sorted(list_excel_courses(path=path, sheet_name=sheet_name), key=lambda course: course.id)
    for excel_course in excel_courses:
        title = excel_course.title.strip()
        if not title:
            skipped += 1
            errors.append(f"Corso Excel ID {excel_course.id}: titolo mancante.")
            continue

        existing = db.scalar(select(Course).where(func.lower(Course.title) == title.lower()))
        if existing:
            if not update_existing:
                skipped += 1
                continue
            updated += 1
            if not dry_run:
                _copy_excel_course_to_model(existing, excel_course)
                db.add(existing)
            continue

        created += 1
        if not dry_run:
            course = Course()
            _copy_excel_course_to_model(course, excel_course)
            db.add(course)

    if dry_run:
        db.rollback()
    else:
        db.commit()

    return ExcelCourseImportResult(created=created, updated=updated, skipped=skipped, errors=errors)


def _copy_excel_course_to_model(course: Course, excel_course) -> None:
    course.title = excel_course.title
    course.short_description = excel_course.short_description
    course.category = excel_course.category
    course.duration = excel_course.duration
    course.status = CourseStatus(excel_course.status)
