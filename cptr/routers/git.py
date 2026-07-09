"""Git API router.

Exposes git operations for the active workspace.
All endpoints require a `root` path (the workspace directory).
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from cptr.utils.git import (
    GitError,
    branches,
    checkout,
    commit,
    create_branch,
    create_worktree,
    delete_branch,
    diff,
    discard,
    fetch,
    is_repo,
    log,
    pull,
    push,
    rename_branch,
    show,
    stage,
    stash_list,
    stash_pop,
    stash_save,
    status,
    uncommit,
    unstage,
    worktrees,
)

router = APIRouter(prefix="/api/git", tags=["git"])


def _handle_git_error(e: GitError) -> None:
    raise HTTPException(status_code=400, detail=str(e))


async def _require_repo(root: str) -> None:
    """Raise 400 if root is not a git repository."""
    if not await is_repo(root):
        raise HTTPException(status_code=400, detail="Not a git repository")


# -- Query endpoints --


@router.get("/status")
async def git_status(root: str):
    """Get branch info and changed files. Returns empty for non-git dirs."""
    if not await is_repo(root):
        return {"is_repo": False, "branch": "", "ahead": 0, "behind": 0, "files": []}
    try:
        result = await status(root)
        result["is_repo"] = True
        return result
    except GitError as e:
        _handle_git_error(e)


@router.get("/diff")
async def git_diff(
    root: str,
    file: Optional[str] = None,
    staged: bool = False,
    untracked: bool = False,
    ignore_whitespace: bool = False,
):
    """Get diff for working tree or staged changes."""
    await _require_repo(root)
    try:
        return await diff(root, file, staged, untracked, ignore_whitespace)
    except GitError as e:
        _handle_git_error(e)


@router.get("/log")
async def git_log(root: str, limit: int = 50, offset: int = 0):
    """Get commit history."""
    await _require_repo(root)
    try:
        return await log(root, limit, offset)
    except GitError as e:
        _handle_git_error(e)


@router.get("/show")
async def git_show(root: str, ref: str, ignore_whitespace: bool = False):
    """Show a single commit with its diff."""
    await _require_repo(root)
    try:
        return await show(root, ref, ignore_whitespace)
    except GitError as e:
        _handle_git_error(e)


@router.get("/branches")
async def git_branches(root: str):
    """List local and remote branches."""
    await _require_repo(root)
    try:
        return await branches(root)
    except GitError as e:
        _handle_git_error(e)


@router.get("/worktrees")
async def git_worktrees(root: str):
    """List git worktrees for the active repository."""
    await _require_repo(root)
    try:
        return await worktrees(root)
    except GitError as e:
        _handle_git_error(e)


@router.get("/stashes")
async def git_stashes(root: str):
    """List stashes."""
    await _require_repo(root)
    try:
        return await stash_list(root)
    except GitError as e:
        _handle_git_error(e)


# -- Mutation endpoints --


class StageRequest(BaseModel):
    root: str
    files: List[str]


class CommitRequest(BaseModel):
    root: str
    message: str


class CheckoutRequest(BaseModel):
    root: str
    branch: str


class CreateBranchRequest(BaseModel):
    root: str
    name: str
    from_ref: Optional[str] = None


class CreateWorktreeRequest(BaseModel):
    root: str
    branch: str
    path: Optional[str] = None


class DeleteBranchRequest(BaseModel):
    root: str
    name: str


class RenameBranchRequest(BaseModel):
    root: str
    old_name: str
    new_name: str


class RootRequest(BaseModel):
    root: str


class PushRequest(BaseModel):
    root: str
    force: bool = False
    set_upstream: bool = False
    branch: Optional[str] = None


class StashSaveRequest(BaseModel):
    root: str
    message: Optional[str] = None


class StashPopRequest(BaseModel):
    root: str
    index: int = 0


@router.post("/stage")
async def git_stage(body: StageRequest):
    """Stage files for commit."""
    try:
        await stage(body.root, body.files)
        return {"ok": True}
    except GitError as e:
        _handle_git_error(e)


@router.post("/unstage")
async def git_unstage(body: StageRequest):
    """Unstage files."""
    try:
        await unstage(body.root, body.files)
        return {"ok": True}
    except GitError as e:
        _handle_git_error(e)


@router.post("/discard")
async def git_discard(body: StageRequest):
    """Discard unstaged changes."""
    try:
        await discard(body.root, body.files)
        return {"ok": True}
    except GitError as e:
        _handle_git_error(e)


@router.post("/commit")
async def git_commit(body: CommitRequest):
    """Create a commit."""
    try:
        return await commit(body.root, body.message)
    except GitError as e:
        _handle_git_error(e)


@router.post("/checkout")
async def git_checkout(body: CheckoutRequest):
    """Switch branch."""
    try:
        await checkout(body.root, body.branch)
        return {"ok": True}
    except GitError as e:
        _handle_git_error(e)


@router.post("/branch")
async def git_create_branch(body: CreateBranchRequest):
    """Create and switch to a new branch."""
    try:
        await create_branch(body.root, body.name, body.from_ref)
        return {"ok": True}
    except GitError as e:
        _handle_git_error(e)


@router.delete("/branch")
async def git_delete_branch(body: DeleteBranchRequest):
    """Delete a local branch."""
    try:
        await delete_branch(body.root, body.name)
        return {"ok": True}
    except GitError as e:
        _handle_git_error(e)


@router.post("/worktrees")
async def git_create_worktree(body: CreateWorktreeRequest):
    """Create a new branch-backed worktree."""
    try:
        return await create_worktree(body.root, body.branch, body.path)
    except GitError as e:
        _handle_git_error(e)


@router.patch("/branch")
async def git_rename_branch(body: RenameBranchRequest):
    """Rename a local branch."""
    try:
        await rename_branch(body.root, body.old_name, body.new_name)
        return {"ok": True}
    except GitError as e:
        _handle_git_error(e)


@router.post("/pull")
async def git_pull(body: RootRequest):
    """Pull from remote."""
    try:
        return await pull(body.root)
    except GitError as e:
        _handle_git_error(e)


@router.post("/fetch")
async def git_fetch(body: RootRequest):
    """Fetch from remote without merging."""
    try:
        return await fetch(body.root)
    except GitError as e:
        _handle_git_error(e)


@router.post("/push")
async def git_push(body: PushRequest):
    """Push to remote."""
    try:
        return await push(body.root, body.force, body.set_upstream, body.branch)
    except GitError as e:
        _handle_git_error(e)


@router.post("/uncommit")
async def git_uncommit(body: RootRequest):
    """Undo the last commit, moving changes back to staging."""
    await _require_repo(body.root)
    try:
        return await uncommit(body.root)
    except GitError as e:
        _handle_git_error(e)


@router.post("/stash")
async def git_stash(body: StashSaveRequest):
    """Stash changes."""
    try:
        return await stash_save(body.root, body.message)
    except GitError as e:
        _handle_git_error(e)


@router.post("/unstash")
async def git_stash_pop(body: StashPopRequest):
    """Pop a stash."""
    try:
        return await stash_pop(body.root, body.index)
    except GitError as e:
        _handle_git_error(e)
