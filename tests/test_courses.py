from __future__ import annotations

import pytest

from app.schemas.course import CourseCreate
from app.schemas.enrollment import EnrollmentCreate
from app.schemas.student import StudentCreate
from app.services.course_service import create_course, delete_course, get_course
from app.services.enrollment_service import create_enrollment
from app.services.student_service import create_student


def test_course_can_be_deleted_without_enrollments(db):
    course = create_course(db, CourseCreate(title="Sicurezza", short_description="", category="IT", duration="2h"))
    delete_course(db, course)
    assert get_course(db, course.id) is None


def test_course_with_enrollments_cannot_be_deleted(db):
    course = create_course(db, CourseCreate(title="Privacy", short_description="", category="Compliance", duration="1h"))
    student = create_student(db, StudentCreate(first_name="Ada", last_name="Rossi", email="ada@example.com"))
    create_enrollment(db, EnrollmentCreate(course_id=course.id, student_id=student.id))
    with pytest.raises(ValueError, match="iscrizioni associate"):
        delete_course(db, course)

