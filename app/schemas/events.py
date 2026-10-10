from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    ticket_id: str
    run_id: str | None
    actor_type: str
    actor_id: str | None
    event_type: str
    detail: dict
    created_at: datetime
