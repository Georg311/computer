/**
 * Git API: status, log, diff, stage, commit, push, pull, branches.
 */
import { fetchJSON, jsonBody } from '$lib/apis';

// Deduplicate concurrent getGitStatus calls.
// Multiple components (layout, GitBar, FileEditor × N) all fetch on mount;
// this ensures they share a single in-flight request and a brief result cache.
const _statusCache = new Map<string, { promise: Promise<unknown>; ts: number }>();
const STATUS_CACHE_MS = 2000;

export const getGitStatus = (root: string): Promise<unknown> => {
	const cached = _statusCache.get(root);
	if (cached && Date.now() - cached.ts < STATUS_CACHE_MS) {
		return cached.promise;
	}
	const promise = fetchJSON(`/api/git/status?root=${encodeURIComponent(root)}`);
	_statusCache.set(root, { promise, ts: Date.now() });
	// Clean up after cache window
	promise.finally(() => {
		setTimeout(() => {
			const entry = _statusCache.get(root);
			if (entry && entry.promise === promise) {
				_statusCache.delete(root);
			}
		}, STATUS_CACHE_MS);
	});
	return promise;
};

/** Force a fresh git status fetch, bypassing the cache. */
export const getGitStatusFresh = (root: string): Promise<unknown> => {
	_statusCache.delete(root);
	return getGitStatus(root);
};

export const getGitLog = (root: string, limit = 30) =>
	fetchJSON(`/api/git/log?root=${encodeURIComponent(root)}&limit=${limit}`);

export const getGitDiff = (params: string) => fetchJSON(`/api/git/diff?${params}`);

export const getGitShow = (root: string, ref: string, ignoreWhitespace = false) =>
	fetchJSON(
		`/api/git/show?root=${encodeURIComponent(root)}&ref=${encodeURIComponent(ref)}&ignore_whitespace=${ignoreWhitespace}`
	);

export const getGitBranches = (root: string) =>
	fetchJSON(`/api/git/branches?root=${encodeURIComponent(root)}`);

export const getGitWorktrees = (root: string) =>
	fetchJSON(`/api/git/worktrees?root=${encodeURIComponent(root)}`);

export const createGitWorktree = (root: string, branch: string, path?: string) =>
	fetchJSON('/api/git/worktrees', jsonBody({ root, branch, path }));

export const getGitStashes = (root: string) =>
	fetchJSON(`/api/git/stashes?root=${encodeURIComponent(root)}`);

export const stageFiles = (root: string, files: string[]) =>
	fetchJSON('/api/git/stage', jsonBody({ root, files }));

export const unstageFiles = (root: string, files: string[]) =>
	fetchJSON('/api/git/unstage', jsonBody({ root, files }));

export const discardChanges = (root: string, files: string[]) =>
	fetchJSON('/api/git/discard', jsonBody({ root, files }));

export const gitCommit = (root: string, message: string) =>
	fetchJSON('/api/git/commit', jsonBody({ root, message }));

export const gitPull = (root: string) => fetchJSON('/api/git/pull', jsonBody({ root }));

export const gitFetch = (root: string) => fetchJSON('/api/git/fetch', jsonBody({ root }));

export const gitPush = (
	root: string,
	{
		force = false,
		set_upstream = false,
		branch
	}: { force?: boolean; set_upstream?: boolean; branch?: string } = {}
) => fetchJSON('/api/git/push', jsonBody({ root, force, set_upstream, branch }));

export const gitUncommit = (root: string) => fetchJSON('/api/git/uncommit', jsonBody({ root }));

export const gitStash = (root: string, message?: string) =>
	fetchJSON('/api/git/stash', jsonBody({ root, message }));

export const gitUnstash = (root: string, index = 0) =>
	fetchJSON('/api/git/unstash', jsonBody({ root, index }));

export const createGitBranch = (root: string, name: string) =>
	fetchJSON('/api/git/branch', jsonBody({ root, name }));

export const renameGitBranch = (root: string, old_name: string, new_name: string) =>
	fetchJSON('/api/git/branch', {
		method: 'PATCH',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ root, old_name, new_name })
	});

export const deleteGitBranch = (root: string, name: string) =>
	fetchJSON('/api/git/branch', {
		method: 'DELETE',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ root, name })
	});

export const checkoutBranch = (root: string, branch: string) =>
	fetchJSON('/api/git/checkout', jsonBody({ root, branch }));

export const stageAll = (root: string) =>
	fetchJSON('/api/git/stage', jsonBody({ root, files: ['.'] }));

export const unstageAll = (root: string) =>
	fetchJSON('/api/git/unstage', jsonBody({ root, files: ['.'] }));
