from typing import Literal
from pydantic import BaseModel, Field

class RunRequest(BaseModel):
    providers: list[Literal["groq", "openrouter"]] = Field(default_factory=lambda: ["groq", "openrouter"])
    limit: int = Field(default=20, ge=1, le=300)
    categories: list[str] = Field(default_factory=list)

class AnnotationRequest(BaseModel):
    run_id: str
    case_id: str
    provider: str
    model: str
    rating: int = Field(ge=1, le=5)
    label: Literal["excellent", "acceptable", "poor", "unsafe", "needs_review"]
    notes: str = ""
    reviewer: str = "anonymous"

class RubricDraftRequest(BaseModel):
    rubric_name: str = Field(min_length=1, max_length=120)
    rubric_json: dict
    source_document: str | None = None
    generation_notes: str = ""
    created_by: str = "system"

class RubricEditRequest(BaseModel):
    rubric_json: dict
    review_notes: str = ""
    reviewer: str = Field(min_length=1, max_length=120)

class RubricDecisionRequest(BaseModel):
    reviewer: str = Field(min_length=1, max_length=120)
    review_notes: str = ""
