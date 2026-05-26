from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enrollment import EnrollmentStatus


class EnrollmentBase(BaseModel):
    course_id: int
    student_id: int
    status: EnrollmentStatus = EnrollmentStatus.non_completato
    notes: str = ""


class EnrollmentCreate(EnrollmentBase):
    pass


class EnrollmentUpdate(BaseModel):
    status: EnrollmentStatus
    notes: str = ""


class EnrollmentRead(EnrollmentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    enrolled_at: datetime
    completed_at: datetime | None
    updated_at: datetime

