"""Shared validation helpers for user-provided financial data."""

from pydantic import BaseModel, Field, field_validator
from datetime import date


class FutureEventInput(BaseModel):
    date: date
    amount: float = Field(gt=0)
    direction: str
    category: str
    event_type: str = "пользовательское событие"
    status: str = "ожидается"
    source: str = "ручной ввод"
    description: str = ""
    account: str = "Основной счёт"

    @field_validator("direction")
    @classmethod
    def valid_direction(cls, value: str) -> str:
        if value not in {"поступление", "списание"}:
            raise ValueError("Направление должно быть «поступление» или «списание».")
        return value

    @field_validator("status")
    @classmethod
    def valid_status(cls, value: str) -> str:
        if value not in {"ожидается", "подтверждено", "исполнено", "отменено"}:
            raise ValueError("Недопустимый статус события.")
        return value
