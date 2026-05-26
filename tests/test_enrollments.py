from __future__ import annotations

import pytest

from app.models.enrollment import EnrollmentStatus
from app.schemas.course import CourseCreate
from app.schemas.enrollment import EnrollmentCreate, EnrollmentUpdate
from app.schemas.student import StudentCreate
from app.services.course_service import create_course
from app.services.enrollment_service import create_enrollment, update_enrollment
from app.services.student_service import create_student


def test_enrollment_is_unique_per_course_and_student(db):
    course = create_course(db, CourseCreate(title="Antincendio", short_description="", category="", duration=""))
    student = create_student(db, StudentCreate(first_name="Sara", last_name="Galli", email="sara@example.com"))
    create_enrollment(db, EnrollmentCreate(course_id=course.id, student_id=student.id))
    with pytest.raises(ValueError, match="già iscritta"):
        create_enrollment(db, EnrollmentCreate(course_id=course.id, student_id=student.id))


def test_completion_date_is_set_and_cleared_by_status(db):
    course = create_course(db, CourseCreate(title="Primo soccorso", short_description="", category="", duration=""))
    student = create_student(db, StudentCreate(first_name="Piero", last_name="Blu", email="piero@example.com"))
    enrollment = create_enrollment(db, EnrollmentCreate(course_id=course.id, student_id=student.id))
    assert enrollment.completed_at is None

    enrollment = update_enrollment(db, enrollment, EnrollmentUpdate(status=EnrollmentStatus.completato, notes="ok"))
    assert enrollment.completed_at is not None

    enrollment = update_enrollment(db, enrollment, EnrollmentUpdate(status=EnrollmentStatus.non_completato, notes="reset"))
    assert enrollment.completed_at is None

