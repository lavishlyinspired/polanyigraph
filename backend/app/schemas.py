"""Shared API schema base: snake_case in Python, camelCase over the wire.

Every response model in this backend should subclass ``ApiModel`` so the JSON
contract matches `frontend/src/lib/api.ts` without hand-aliasing each field.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
