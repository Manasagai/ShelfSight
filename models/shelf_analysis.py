from typing import Literal

from pydantic import BaseModel, Field


Severity = Literal["Low", "Medium", "High"]


class DetectedIssue(BaseModel):
    issue: str = Field(min_length=1)
    severity: Severity
    evidence: str = Field(min_length=1)
    recommendation: str = Field(min_length=1)


class Recommendation(BaseModel):
    action: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    priority: Severity


class EmptySpace(BaseModel):
    position: str = Field(min_length=1)
    size: str = Field(default="visible", min_length=1)


class ShelfProduct(BaseModel):
    label: str = Field(min_length=1)
    approximate_position: str = Field(default="unclear", min_length=1)
    group: str = Field(default="Product Group", min_length=1)
    facing_count: int | None = Field(default=None, ge=1)
    visibility: str = Field(default="visible", min_length=1)


class ShelfRow(BaseModel):
    row_number: int = Field(ge=1)
    vertical_zone: Literal["Top", "Eye Level", "Hand Level", "Lower Level", "Unclear"] = "Unclear"
    products: list[ShelfProduct] = Field(default_factory=list)
    empty_spaces: list[EmptySpace] = Field(default_factory=list)


class ShelfAnalysis(BaseModel):
    overall_score: int = Field(ge=0, le=100)
    visibility_score: int = Field(ge=0, le=100)
    organization_score: int = Field(ge=0, le=100)
    space_utilization_score: int = Field(ge=0, le=100)
    presentation_score: int = Field(ge=0, le=100)
    detected_products: list[str] = Field(default_factory=list)
    detected_issues: list[DetectedIssue] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)
    priority_actions: list[Recommendation] = Field(default_factory=list)
    summary: str = Field(min_length=1)
    shelf_rows: list[ShelfRow] = Field(default_factory=list)


class CategoryPlacement(BaseModel):
    category: str = Field(min_length=1)
    recommended_zone: Literal["Top", "Eye Level", "Hand Level", "Lower Level", "Bottom"] = "Eye Level"
    reason: str = Field(min_length=1)
    tip: str = Field(default="", min_length=0)


class EmptyShelfPlan(BaseModel):
    shelf_count: int = Field(default=4, ge=1)
    summary: str = Field(min_length=1)
    placements: list[CategoryPlacement] = Field(default_factory=list)

