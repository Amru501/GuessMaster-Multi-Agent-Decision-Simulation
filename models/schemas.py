"""Pydantic schemas for LLM persona responses."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class PersonaLLMResponse(BaseModel):
    decision: Literal["ADD", "REJECT"]
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str

    @field_validator("reason")
    @classmethod
    def reason_not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("reason must not be blank")
        return stripped


def parse_persona_response(content: str) -> PersonaLLMResponse:
    """Parse and validate raw JSON from an LLM response."""
    return PersonaLLMResponse.model_validate_json(content)
