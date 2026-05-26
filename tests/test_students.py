from __future__ import annotations

import pytest

from app.schemas.course import CourseCreate
from app.schemas.enrollment import EnrollmentCreate
from app.schemas.student import StudentCreate
from app.services.course_service import create_course
from app.services.enrollment_service import create_enrollment
from app.services.student_service import create_student, delete_student


def test_student_email_is_unique(db):
    create_student(db, StudentCreate(first_name="Luca", last_name="Bianchi", email="luca@example.com"))
    with pytest.raises(ValueError, match="Email già presente"):
        create_student(db, StudentCreate(first_name="Luca", last_name="Verdi", email="luca@example.com"))


def test_student_with_enrollments_cannot_be_deleted(db):
    course = create_course(db, CourseCreate(title="Qualità", short_description="", category="", duration=""))
    student = create_student(db, StudentCreate(first_name="Marta", last_name="Neri", email="marta@example.com"))
    create_enrollment(db, EnrollmentCreate(course_id=course.id, student_id=student.id))
    with pytest.raises(ValueError, match="iscrizioni associate"):
        delete_student(db, student)

