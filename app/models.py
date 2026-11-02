
import re
from datetime import date
from pydantic import BaseModel, ConfigDict, Field, field_validator


class EmployeeCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    emp_code: str = Field(
        min_length=7,
        max_length=9,
        pattern=r"^EMP\d{4,6}$",
    )
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(
        min_length=1,
        max_length=120,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    )
    department: str = Field(min_length=1, max_length=50)
    shift_start: str = "09:30"
    shift_end: str = "18:30"
    joined_on: date

    @field_validator("shift_start", "shift_end")
    @classmethod
    def validate_shift_time(cls, value: str) -> str:
        if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", value):
            raise ValueError("Time must use HH:MM format.")
        return value

    @field_validator("shift_end")
    @classmethod
    def validate_shift_end(cls, value: str, info):
        start = info.data.get("shift_start")
        if start == value:
            raise ValueError("shift_start and shift_end must differ.")
        return value
