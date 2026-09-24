from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class OrganizationDTO:
    id: str
    name: str
    is_active: bool
    owner_id: Optional[int]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, model):

        return cls(
            id=str(model.id),
            name=model.name,
            is_active=model.is_active,
            owner_id=model.owner_id,
            created_at=model.created_at,
            updated_at=model.updated_at
        )
