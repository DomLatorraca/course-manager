from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MaterialRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    title: str
    description: str
    original_filename: str
    stored_filename: str
    size_bytes: int
    uploaded_at: datetime

