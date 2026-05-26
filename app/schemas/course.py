from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.course import CourseStatus


class CourseBase(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    short_description: str = ""
    category: str = ""
    duration: str = ""
    status: CourseStatus = CourseStatus.attivo


class CourseCreate(CourseBase):
    pass


class CourseUpdate(CourseBase):
    pass


class CourseRead(CourseBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime

