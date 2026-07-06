"""Skills API: lightweight read-only endpoint for the $ mention picker."""

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


@router.get("", response_model=list[SkillResponse])
async def list_skills(workspace: str = Query(..., description="Workspace path")):
    """List available skills (frontmatter only) for the $ mention picker."""
    from cptr.utils.skills import discover_skills

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
        )
        for s in skills
    ]
