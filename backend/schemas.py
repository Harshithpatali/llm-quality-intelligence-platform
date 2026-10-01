from pydantic import BaseModel, Field
from typing import Literal

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
