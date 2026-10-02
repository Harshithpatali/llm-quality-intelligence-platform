from typing import Literal

from pydantic import BaseModel, Field


class RunRequest(BaseModel):
    providers: list[Literal["groq", "openrouter"]] = Field(
        default_factory=lambda: ["groq", "openrouter"]
    )
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


class RubricGenerateRequest(BaseModel):
    rubric_name: str = Field(min_length=1, max_length=120)
    objective: str = Field(min_length=10, max_length=4000)
    policy_id: str | None = None
    source_document: str | None = None
    created_by: str = Field(default="system", min_length=1, max_length=120)


class CatalogEvaluationRequest(BaseModel):
    item_id: str = Field(min_length=1, max_length=120)
    domain_name: str = Field(min_length=1, max_length=120)
    user_query: str = Field(min_length=3, max_length=2000)
    providers: list[Literal["groq", "openrouter"]] = Field(
        default_factory=lambda: ["groq", "openrouter"]
    )
    rubric_id: str | None = None
    rubric_json: dict | None = None
    policy_id: str | None = None


class ReviewQueueRequest(BaseModel):
    trace_id: str = Field(min_length=1, max_length=120)
    priority: int = Field(default=0, ge=0, le=100)


class ReviewClaimRequest(BaseModel):
    reviewer: str = Field(min_length=1, max_length=120)


class OperationalAnnotationRequest(BaseModel):
    task_id: str | None = None
    trace_id: str | None = None
    review_id: str | None = None
    annotator_id: str = Field(min_length=1, max_length=120)
    sop_id: str
    relevance: Literal["pass", "minor_issue", "major_issue", "not_applicable"]
    correctness: Literal["pass", "minor_issue", "major_issue", "not_applicable"]
    completeness: Literal["pass", "minor_issue", "major_issue", "not_applicable"]
    overall_label: Literal["accept", "revise", "reject", "escalate"]
    evidence: str = Field(min_length=8, max_length=4000)
    defect_category: str = "none"
    confidence: int = Field(ge=1, le=5)
    handling_seconds: int = Field(ge=0, le=86400)
    escalated: bool = False
    is_audit: bool = False
