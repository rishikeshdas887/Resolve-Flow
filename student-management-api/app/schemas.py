"""Pydantic request/response schemas and validation rules for student records."""

import re
from datetime import date

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

# Characters commonly used when writing phone numbers; digits are counted separately.
_PHONE_CHARS = re.compile(r"^\+?[0-9 ().\-]+$")

_MIN_BIRTH_DATE = date(1900, 1, 1)


def _check_date_of_birth(value: date) -> date:
    today = date.today()
    if value < _MIN_BIRTH_DATE:
        raise ValueError("date_of_birth must be on or after 1900-01-01")
    if value > today:
        raise ValueError("date_of_birth cannot be in the future")
    return value


def _check_phone(value: str | None) -> str | None:
    if value is None:
        return value
    digits = re.sub(r"\D", "", value)
    if not _PHONE_CHARS.fullmatch(value) or not 7 <= len(digits) <= 15:
        raise ValueError("phone must contain 7-15 digits and only '+()-. ' separators")
    return value


class StudentBase(BaseModel):
    """Every student field except the ID; also used as the PUT request body."""

    model_config = ConfigDict(str_strip_whitespace=True)

    full_name: str = Field(min_length=2, max_length=100, examples=["Asha Verma"])
    date_of_birth: date = Field(examples=["2004-05-12"])
    email: EmailStr | None = Field(default=None, examples=["asha.verma@example.com"])
    phone: str | None = Field(default=None, examples=["+91 98765 43210"])
    course: str | None = Field(default=None, max_length=100, examples=["Computer Science"])
    address: str | None = Field(default=None, max_length=255, examples=["12 Lake Road, Pune"])
    enrollment_date: date | None = Field(default=None, examples=["2024-08-01"])

    @field_validator("date_of_birth")
    @classmethod
    def _dob_not_in_future(cls, value: date) -> date:
        return _check_date_of_birth(value)

    @field_validator("phone")
    @classmethod
    def _phone_shape(cls, value: str | None) -> str | None:
        return _check_phone(value)

    @model_validator(mode="after")
    def _contact_and_dates_consistent(self) -> "StudentBase":
        if self.email is None and self.phone is None:
            raise ValueError("at least one contact method is required: email or phone")
        if self.enrollment_date is not None and self.enrollment_date < self.date_of_birth:
            raise ValueError("enrollment_date cannot be earlier than date_of_birth")
        return self


class StudentCreate(StudentBase):
    """POST /students request body. ``student_id`` is unique and chosen by the caller."""

    student_id: str = Field(
        min_length=1,
        max_length=32,
        pattern=r"^[A-Za-z0-9_-]+$",
        examples=["STU001"],
    )


class StudentPatch(BaseModel):
    """PATCH /students/{id} request body — every field optional.

    Cross-field rules (contact required, enrollment >= birth date) are
    re-validated against the merged record in the route.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    full_name: str | None = Field(default=None, min_length=2, max_length=100)
    date_of_birth: date | None = None
    email: EmailStr | None = None
    phone: str | None = None
    course: str | None = Field(default=None, max_length=100)
    address: str | None = Field(default=None, max_length=255)
    enrollment_date: date | None = None

    @field_validator("date_of_birth")
    @classmethod
    def _dob_not_in_future(cls, value: date | None) -> date | None:
        return _check_date_of_birth(value) if value is not None else value

    @field_validator("phone")
    @classmethod
    def _phone_shape(cls, value: str | None) -> str | None:
        return _check_phone(value)


class StudentOut(StudentCreate):
    """Response body for a stored student."""

    model_config = ConfigDict(from_attributes=True)
