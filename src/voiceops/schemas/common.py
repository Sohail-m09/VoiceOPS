from pydantic import BaseModel, ConfigDict


class RequestModel(BaseModel):
    """Base schema for validating incoming API requests."""

    model_config = ConfigDict(extra="forbid")


class ORMResponse(BaseModel):
    """Base schema for validating responses from ORM objects."""

    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
    )
