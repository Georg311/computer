"""Skills API: lightweight endpoint for the $ mention picker."""

from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter(prefix="/api/skills", tags=["skills"])


class SkillResponse(BaseModel):
    name: str
    description: str
    location: str
    source: str  # "workspace" or "global"
    license: Optional[str] = None
    compatibility: Optional[str] = None
    managed: bool = False
    created_by: Optional[str] = None
    created_from: Optional[str] = None
    view_count: int = 0
    use_count: int = 0
    update_count: int = 0
    last_viewed_at: Optional[str] = None
    last_used_at: Optional[str] = None
    last_updated_at: Optional[str] = None


@router.get("", response_model=list[SkillResponse])
async def list_skills(
    workspace: str = Query("", description="Workspace path; omit for global skills"),
):
    """List available skills (frontmatter only) for the $ mention picker."""
    from cptr.models import Config
    from cptr.utils.skills import discover_skills

    if (await Config.get("skills.enabled")) in (False, "false", "0"):
        return []

    skills = await asyncio.to_thread(discover_skills, workspace)
    return [
        SkillResponse(
            name=s.name,
            description=s.description,
            location=s.location,
            source=s.source,
            license=s.license,
            compatibility=s.compatibility,
            managed=s.managed,
            created_by=s.created_by,
            created_from=s.created_from,
            view_count=s.view_count,
            use_count=s.use_count,
            update_count=s.update_count,
            last_viewed_at=s.last_viewed_at,
            last_used_at=s.last_used_at,
            last_updated_at=s.last_updated_at,
        )
        for s in skills
    ]
