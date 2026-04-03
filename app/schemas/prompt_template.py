"""
Pydantic schemas for PromptTemplate — Sprint IA-1.

Validacao estrita de entrada/saida para a API de gerenciamento de prompts.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.prompt_template import PromptCategory, PromptRole


class PromptTemplateCreate(BaseModel):
    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z][a-z0-9_]*$")
    category: PromptCategory
    role: PromptRole
    content: str = Field(..., min_length=1)
    tenant_id: Optional[int] = None
    input_schema: Optional[dict[str, Any]] = None
    output_schema: Optional[dict[str, Any]] = None
    model_hint: Optional[str] = Field(None, max_length=100)
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=1, le=32768)


class PromptTemplateUpdate(BaseModel):
    content: str = Field(..., min_length=1)
    input_schema: Optional[dict[str, Any]] = None
    output_schema: Optional[dict[str, Any]] = None
    model_hint: Optional[str] = Field(None, max_length=100)
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=1, le=32768)


class PromptTemplateRead(BaseModel):
    id: int
    tenant_id: Optional[int]
    slug: str
    category: PromptCategory
    role: PromptRole
    version: int
    content: str
    input_schema: Optional[dict[str, Any]]
    output_schema: Optional[dict[str, Any]]
    model_hint: Optional[str]
    temperature: Optional[float]
    max_tokens: Optional[int]
    is_active: bool
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)
