from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Question(StrictModel):
    question: str = Field(min_length=3, max_length=2000)
    dataset_id: str = "tpch_orders"

    @field_validator("question")
    @classmethod
    def clean_question(cls, value: str) -> str:
        if len(value.strip()) < 3:
            raise ValueError("Enter a question with at least three non-space characters.")
        return value.strip()


class Filter(StrictModel):
    field: str = Field(min_length=1, max_length=80)
    operator: Literal["eq", "ne", "gt", "gte", "lt", "lte", "in", "between"]
    values: list[str | int] = Field(min_length=1, max_length=30)

    @field_validator("values", mode="before")
    @classmethod
    def check_values(cls, values):
        if not isinstance(values, list) or any(
            type(v) not in (str, int) or (isinstance(v, str) and len(v) > 200) for v in values
        ):
            raise ValueError("Filter values must be short strings or integers.")
        return values

    @model_validator(mode="after")
    def check_arity(self):
        expected = 2 if self.operator == "between" else 1
        if self.operator != "in" and len(self.values) != expected:
            raise ValueError("Invalid number of filter values.")
        return self


class Sort(StrictModel):
    field: str = Field(min_length=1, max_length=80)
    direction: Literal["asc", "desc"] = "desc"


class Plan(StrictModel):
    status: Literal["query", "needs_clarification", "unsupported"]
    message: str = Field(default="", max_length=1000)
    metrics: list[str] = Field(default_factory=list, max_length=20)
    dimensions: list[str] = Field(default_factory=list, max_length=3)
    filters: list[Filter] = Field(default_factory=list, max_length=10)
    sort: list[Sort] = Field(default_factory=list, max_length=3)
    limit: int = Field(default=20, ge=1, le=500, strict=True)
    analysis: Literal["aggregate", "compare", "share", "above_average"] = "aggregate"
    time_selection: Literal["explicit", "latest_available"] = "explicit"
    reference_filters: list[Filter] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def check_plan(self):
        if self.status == "query" and not self.metrics:
            raise ValueError("A query needs at least one metric.")
        if self.status != "query" and not self.message.strip():
            raise ValueError("Clarifications and unsupported requests need a message.")
        if len(set(self.metrics)) != len(self.metrics):
            raise ValueError("Duplicate metrics.")
        if len(set(self.dimensions)) != len(self.dimensions):
            raise ValueError("Duplicate dimensions.")
        if self.status == "query":
            if self.time_selection == "latest_available" and self.analysis != "aggregate":
                raise ValueError("Latest available time requires a grouped or scalar aggregate.")
            if self.analysis == "aggregate" and self.reference_filters:
                raise ValueError("Aggregate plans cannot contain unused reference filters.")
            if self.analysis != "aggregate" and len(self.metrics) != 1:
                raise ValueError("Multi-step analysis requires exactly one metric.")
            if self.analysis in ("compare", "share") and (self.dimensions or self.sort):
                raise ValueError("Scalar comparisons/shares cannot group or sort.")
            if self.analysis == "above_average" and len(self.dimensions) != 1:
                raise ValueError("Above-average analysis requires exactly one grouping dimension.")
        return self
