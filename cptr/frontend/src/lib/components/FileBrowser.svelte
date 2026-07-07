<script module>
	// Module-level cache: survives component destroy/create cycles
	const _treeExpandedCache = new Map();
	const _treeContentsCache = new Map();
</script>

<script lang="ts">
	import { activeWorkspace, setFileBrowserCwd, openFileTab, openPreviewTab } from '$lib/stores';
	import { gitStatusStore, type GitFile } from '$lib/stores/gitStatus.svelte';
	import { systemEvents } from '$lib/stores/systemEvents.svelte';
	import { tooltip } from '$lib/tooltip';
	import {
		listDir,
		downloadArchive,
		deleteFiles,
		moveFile,
		uploadFiles as apiUpload,
		createEntry
	} from '$lib/apis/files';
	import { fileIconName } from '$lib/utils/fileIcon';
	import Icon from './Icon.svelte';
	import Spinner from './common/Spinner.svelte';
	import DropdownMenu from './DropdownMenu.svelte';
	import { t } from '$lib/i18n';
	import { TAB_DRAG_MIME } from '$lib/constants';

	interface FileEntry {
		name: string;
		type: string;
		size: number | null;
		modified: string | null;
	}

	interface TreeEntry extends FileEntry {
		path: string;
		depth: number;
	}

	let entries = $state<FileEntry[]>([]);
	let loading = $state(false);
	let initialLoad = $state(true);
	let fetchTimer: ReturnType<typeof setTimeout> | null = null;
	let fetching = false;
	let dragExpandTimer: ReturnType<typeof setTimeout> | null = null;
	let error = $state<string | null>(null);
	let searchQuery = $state('');
	let dragOverDir = $state<string | null>(null);
	let draggedItem = $state<string | null>(null);
	let showNewInput = $state<'file' | 'folder' | null>(null);
	let newName = $state('');
	let dropzoneActive = $state(false);
	let addMenuOpen = $state(false);
	let showHidden = $state(
		typeof localStorage !== 'undefined' && localStorage.getItem('fileBrowser:showHidden') === 'true'
	);
	let sortMenuOpen = $state(false);
	let sortBtnEl: HTMLButtonElement | undefined = $state();
	let addBtnEl: HTMLButtonElement | undefined = $state();

	// Tree view
	let expandedDirs = $state<Set<string>>(new Set());
	let dirContents = $state<Map<string, FileEntry[]>>(new Map());

	// Sort
	let sortBy = $state<'name' | 'size' | 'modified'>('name');
	let sortDir = $state<'asc' | 'desc'>('asc');

	// Multi-select
	let selectedPaths = $state<Set<string>>(new Set());
	let lastClickedIndex = $state<number>(-1);
	let dragOverBreadcrumb = $state<string | null>(null);

	// Context menu
	let contextMenu = $state<{ x: number; y: number; entry: TreeEntry; anchor?: HTMLElement } | null>(
		null
	);
	let renamingEntry = $state<string | null>(null);
	let renameValue = $state('');

	let cwd = $derived($activeWorkspace?.fileBrowserCwd ?? $activeWorkspace?.path ?? '/');
	let workspacePath = $derived($activeWorkspace?.path ?? '/');
	let gitStatus = $derived(gitStatusStore.status);
	let gitRoot = $derived(workspacePath.replace(/\/$/, ''));

	// Ports from this workspace's terminals
	let workspacePorts = $derived(
		systemEvents.ports.filter(
			(p) =>
				p.session_id &&
				$activeWorkspace?.groups.some((g) => g.tabs.some((t) => t.sessionId === p.session_id))
		)
	);

	let breadcrumbs = $derived(() => {
		if (!cwd || !workspacePath) return [];
		const wsName = $activeWorkspace?.name ?? 'workspace';
		const relative = cwd.startsWith(workspacePath) ? cwd.slice(workspacePath.length) : '';
		const parts = relative.split('/').filter(Boolean);
		const segments = [{ name: wsName, path: workspacePath }];
		let current = workspacePath;
		for (const part of parts) {
			current = current + '/' + part;
			segments.push({ name: part, path: current });
		}
		return segments;
	});

	function normalizeGitPath(path: string): string {
		return path.replace(/^\/+/, '').replace(/\/$/, '');
	}

	function toGitRelativePath(path: string): string {
		if (!gitRoot) return normalizeGitPath(path);
		if (path === gitRoot) return '';
		if (path.startsWith(gitRoot + '/')) return normalizeGitPath(path.slice(gitRoot.length + 1));
		return normalizeGitPath(path);
	}

	function gitStatusRank(status: string): number {
		switch (status) {
			case 'conflict':
				return 7;
			case 'deleted':
				return 6;
			case 'renamed':
				return 5;
			case 'added':
			case 'untracked':
				return 4;
			case 'modified':
			case 'type-changed':
				return 3;
			case 'copied':
				return 2;
			default:
				return 1;
		}
	}

	function pickGitStatus(current: GitFile | undefined, next: GitFile): GitFile {
		if (!current) return next;
		return gitStatusRank(next.status) > gitStatusRank(current.status) ? next : current;
	}

	let gitFilesByPath = $derived.by(() => {
		const files = new Map<string, GitFile>();
		if (!gitStatus?.is_repo) return files;
		for (const file of gitStatus.files ?? []) {
			files.set(normalizeGitPath(file.path), file);
		}
		return files;
	});

	let gitDirsByPath = $derived.by(() => {
		const dirs = new Map<string, GitFile>();
		if (!gitStatus?.is_repo || !gitRoot) return dirs;

		for (const file of gitStatus.files ?? []) {
			const parts = normalizeGitPath(file.path).split('/').filter(Boolean);
			parts.pop();
			let current = gitRoot;
			for (const part of parts) {
				current = `${current}/${part}`;
				dirs.set(current, pickGitStatus(dirs.get(current), file));
			}
		}

		return dirs;
	});

	function gitStatusForFile(entry: TreeEntry): GitFile | undefined {
		if (!gitStatus?.is_repo) return undefined;
		if (entry.type === 'directory') return undefined;

		const relativePath = toGitRelativePath(entry.path);
		return gitFilesByPath.get(relativePath);
	}

	function gitStatusForDirectory(entry: TreeEntry): GitFile | undefined {
		if (!gitStatus?.is_repo) return undefined;
		if (entry.type !== 'directory') return undefined;

		return gitDirsByPath.get(entry.path.replace(/\/$/, ''));
	}

	function gitStatusDecoration(status: string): {
		char: string;
		nameColor: string;
		badgeColor: string;
		markerColor: string;
		label: string;
	} {
		switch (status) {
			case 'added':
				return {
					char: 'A',
					nameColor: 'text-emerald-700/85 dark:text-emerald-300/85',
					badgeColor: 'text-emerald-600/85 dark:text-emerald-300/85',
					markerColor: 'bg-emerald-500/70',
					label: 'Added'
				};
			case 'untracked':
				return {
					char: 'U',
					nameColor: 'text-[#476f36] dark:text-[#91bd91]',
					badgeColor: 'text-[#4f7b35] dark:text-[#7fbf8b]',
					markerColor: 'bg-[#7fbf8b]/70',
					label: 'Untracked'
				};
			case 'modified':
				return {
					char: 'M',
					nameColor: 'text-[#735c2a] dark:text-[#c7ad78]',
					badgeColor: 'text-[#815f23] dark:text-[#d2ba82]',
					markerColor: 'bg-[#d2ba82]/70',
					label: 'Modified'
				};
			case 'deleted':
				return {
					char: 'D',
					nameColor: 'text-rose-600/85 dark:text-rose-300/85',
					badgeColor: 'text-rose-500/85 dark:text-rose-300/85',
					markerColor: 'bg-rose-500/70',
					label: 'Deleted'
				};
			case 'renamed':
				return {
					char: 'R',
					nameColor: 'text-sky-600/85 dark:text-sky-300/85',
					badgeColor: 'text-sky-500/85 dark:text-sky-300/85',
					markerColor: 'bg-sky-500/70',
					label: 'Renamed'
				};
			case 'copied':
				return {
					char: 'C',
					nameColor: 'text-sky-600/80 dark:text-sky-300/80',
					badgeColor: 'text-sky-500/80 dark:text-sky-300/80',
					markerColor: 'bg-sky-500/65',
					label: 'Copied'
				};
			case 'type-changed':
				return {
					char: 'T',
					nameColor: 'text-violet-600/80 dark:text-violet-300/80',
					badgeColor: 'text-violet-500/80 dark:text-violet-300/80',
					markerColor: 'bg-violet-500/65',
					label: 'Type changed'
				};
			case 'conflict':
				return {
					char: '!',
					nameColor: 'text-orange-600/90 dark:text-orange-300/90',
					badgeColor: 'text-orange-500/90 dark:text-orange-300/90',
					markerColor: 'bg-orange-500/75',
					label: 'Conflict'
				};
			default:
				return {
					char: '?',
					nameColor: 'text-gray-700 dark:text-gray-300',
					badgeColor: 'text-gray-500/80 dark:text-gray-400/80',
					markerColor: 'bg-gray-400/70',
					label: 'Changed'
				};
		}
	}

	function gitStatusTooltip(file: GitFile, entry: TreeEntry): string {
		const badge = gitStatusDecoration(file.status);
		const scope = entry.type === 'directory' ? 'contains ' : '';
		const state =
			file.staged && file.unstaged ? 'staged and unstaged' : file.staged ? 'staged' : 'unstaged';
		return `${scope}${badge.label} (${state})`;
	}

	// Fetch directory on cwd change
	let _prevCwd = '';
	$effect(() => {
		if (cwd) {
			if (cwd !== _prevCwd) {
				const isNavigation = _prevCwd !== '';
				_prevCwd = cwd;
				if (isNavigation) {
					// Navigated to a new directory: reset tree state
					expandedDirs = new Set();
					dirContents = new Map();
					initialLoad = true;
				} else {
					// Component (re)mount: restore tree state from cache
					const cachedExpanded = _treeExpandedCache.get(cwd);
					if (cachedExpanded) {
						expandedDirs = new Set(cachedExpanded);
						dirContents = new Map(_treeContentsCache.get(cwd) ?? []);
					}
				}
				fetchDirectoryImmediate(cwd);
			}
		}
	});

	// Keep the websocket watch path in sync (separate effect so it doesn't
	// re-trigger directory fetches via fsTick feedback loops)
	$effect(() => {
		if (cwd) {
			systemEvents.connect(cwd);
		}
	});

	// Auto-refresh on filesystem changes (debounced, silent)
	$effect(() => {
		const _tick = systemEvents.fsTick; // subscribe
		if (_tick > 0 && cwd && !fetching && systemEvents.isRelevantFsChange(cwd)) {
			// Use a longer debounce for auto-refresh to batch rapid fs events
			debouncedFetch(cwd, 800);
			// Also refresh expanded directories
			for (const dir of expandedDirs) {
				fetchSubdir(dir);
			}
		}
	});

	function toggleHidden() {
		showHidden = !showHidden;
		localStorage.setItem('fileBrowser:showHidden', String(showHidden));
		fetchDirectory(cwd);
		// Clear cache and re-fetch expanded dirs with new filter
		dirContents = new Map();
		for (const dir of expandedDirs) {
			fetchSubdir(dir);
		}
	}

	function debouncedFetch(path: string, delay = 300) {
		if (fetchTimer) clearTimeout(fetchTimer);
		fetchTimer = setTimeout(() => {
			fetchTimer = null;
			fetchDirectoryImmediate(path);
		}, delay);
	}

	async function fetchDirectoryImmediate(path: string) {
		if (fetchTimer) clearTimeout(fetchTimer);
		fetchTimer = null;
		if (fetching) return; // skip overlapping fetches
		fetching = true;
		// Only show the loading spinner on initial load (no entries yet).
		// Background refreshes silently update entries in-place.
		const isInitial = entries.length === 0;
		if (isInitial) loading = true;
		error = null;
		try {
			const data = await listDir(path);
			// Only apply if still viewing the same directory
			if (path === cwd) {
				entries = showHidden
					? data.entries
					: data.entries.filter((e: FileEntry) => !e.name.startsWith('.'));
			}
		} catch (e: any) {
			if (path === cwd) {
				error = e.message || $t('files.failedToLoad');
				entries = [];
			}
		} finally {
			loading = false;
			initialLoad = false;
			fetching = false;
		}
	}

	/** Backward-compatible alias used by action handlers (delete, rename, etc.) */
	function fetchDirectory(path: string) {
		debouncedFetch(path);
	}

	// ── Tree view: expand/collapse ─────────────────────────────
	function saveTreeCache() {
		if (cwd) {
			_treeExpandedCache.set(cwd, [...expandedDirs]);
			_treeContentsCache.set(cwd, [...dirContents.entries()]);
		}
	}

	async function toggleDir(path: string) {
		if (expandedDirs.has(path)) {
			const next = new Set(expandedDirs);
			next.delete(path);
			expandedDirs = next;
		} else {
			if (!dirContents.has(path)) {
				await fetchSubdir(path);
			}
			const next = new Set(expandedDirs);
			next.add(path);
			expandedDirs = next;
		}
		saveTreeCache();
	}

	async function fetchSubdir(path: string) {
		try {
			const data = await listDir(path);
			const filtered = showHidden
				? data.entries
				: data.entries.filter((e: FileEntry) => !e.name.startsWith('.'));
			dirContents = new Map(dirContents).set(path, filtered);
			saveTreeCache();
		} catch {
			// Remove from expanded on error
			const next = new Set(expandedDirs);
			next.delete(path);
			expandedDirs = next;
			const nextContents = new Map(dirContents);
			nextContents.delete(path);
			dirContents = nextContents;
			saveTreeCache();
		}
	}

	/** Refresh a specific expanded directory's cached contents */
	async function refreshParentDir(entryPath: string) {
		const parentDir = entryPath.substring(0, entryPath.lastIndexOf('/'));
		if (parentDir === cwd || parentDir === cwd.replace(/\/$/, '')) {
			fetchDirectory(cwd);
		} else if (dirContents.has(parentDir)) {
			await fetchSubdir(parentDir);
		}
	}

	function handleClick(e: MouseEvent, entry: TreeEntry, index: number) {
		// Multi-select with ctrl/cmd or shift
		if (e.metaKey || e.ctrlKey) {
			const next = new Set(selectedPaths);
			if (next.has(entry.path)) next.delete(entry.path);
			else next.add(entry.path);
			selectedPaths = next;
			lastClickedIndex = index;
			return;
		}

		if (e.shiftKey && lastClickedIndex >= 0) {
			const list = visibleEntries;
			const start = Math.min(lastClickedIndex, index);
			const end = Math.max(lastClickedIndex, index);
			const next = new Set(selectedPaths);
			for (let i = start; i <= end; i++) {
				next.add(list[i].path);
			}
			selectedPaths = next;
			return;
		}

		// Normal click, clear selection and act
		selectedPaths = new Set();
		lastClickedIndex = index;
		if (entry.type === 'directory') {
			// Navigate into the folder
			setFileBrowserCwd(entry.path);
		} else {
			openFileTab(entry.path);
		}
	}

	function navigateTo(path: string) {
		setFileBrowserCwd(path);
	}

	// fileIconName imported from $lib/utils/fileIcon

	function formatSize(bytes: number | null): string {
		if (bytes === null || bytes === undefined) return '';
		if (bytes < 1024) return `${bytes} B`;
		if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
		return `${(bytes / 1048576).toFixed(1)} MB`;
	}

	// ── Tree-aware visible entries ──────────────────────────────
	function sortItems(items: FileEntry[]): FileEntry[] {
		const dirs = items.filter((e) => e.type === 'directory');
		const files = items.filter((e) => e.type !== 'directory');

		function compare(a: FileEntry, b: FileEntry): number {
			let result = 0;
			if (sortBy === 'name') {
				result = a.name.toLowerCase().localeCompare(b.name.toLowerCase());
			} else if (sortBy === 'size') {
				result = (a.size ?? 0) - (b.size ?? 0);
			} else if (sortBy === 'modified') {
				result = (a.modified ?? '').localeCompare(b.modified ?? '');
			}
			return sortDir === 'asc' ? result : -result;
		}

		dirs.sort(compare);
		files.sort(compare);
		return [...dirs, ...files];
	}

	let visibleEntries = $derived.by(() => {
		const result: TreeEntry[] = [];
		const query = searchQuery.toLowerCase();

		function walk(parentPath: string, items: FileEntry[], depth: number) {
			let filtered = query ? items.filter((e) => e.name.toLowerCase().includes(query)) : items;
			for (const entry of sortItems(filtered)) {
				const fullPath = parentPath.endsWith('/')
					? parentPath + entry.name
					: parentPath + '/' + entry.name;
				result.push({ ...entry, path: fullPath, depth });
				if (entry.type === 'directory' && expandedDirs.has(fullPath)) {
					const children = dirContents.get(fullPath);
					if (children) walk(fullPath, children, depth + 1);
				}
			}
		}

		walk(cwd, entries, 0);
		return result;
	});

	function toggleSort(field: 'name' | 'size' | 'modified') {
		if (sortBy === field) {
			sortDir = sortDir === 'asc' ? 'desc' : 'asc';
		} else {
			sortBy = field;
			sortDir = 'asc';
		}
	}

	function clearSelection() {
		selectedPaths = new Set();
		lastClickedIndex = -1;
	}

	function selectAll() {
		const all = new Set<string>();
		for (const e of visibleEntries) {
			all.add(e.path);
		}
		selectedPaths = all;
	}

	async function archiveSelected() {
		if (selectedPaths.size === 0) return;
		try {
			const res = await downloadArchive([...selectedPaths]);
			if (!res.ok) return;
			const disposition = res.headers.get('content-disposition') ?? '';
			const match = disposition.match(/filename="?([^"]+)"?/);
			const filename = match?.[1] ?? 'archive.zip';
			const blob = await res.blob();
			const url = URL.createObjectURL(blob);
			const a = document.createElement('a');
			a.href = url;
			a.download = filename;
			a.click();
			URL.revokeObjectURL(url);
		} catch {}
		clearSelection();
	}

	async function deleteSelected() {
		if (selectedPaths.size === 0) return;
		if (!confirm($t('files.deleteItemConfirm', { count: selectedPaths.size }))) return;
		for (const path of selectedPaths) {
			try {
				await deleteFiles([path]);
			} catch {}
		}
		clearSelection();
		fetchDirectory(cwd);
	}

	// ── Drag to move ────────────────────────────────────────────

	function isTabDrag(e: DragEvent): boolean {
		return Boolean(
			e.dataTransfer?.types.includes(TAB_DRAG_MIME) || e.dataTransfer?.types.includes('text/tab-id')
		);
	}

	/** Collect all paths being dragged: either selected items (if the dragged item is selected) or just the single item */
	function getDraggedPaths(entry: TreeEntry): string[] {
		if (selectedPaths.size > 0 && selectedPaths.has(entry.path)) {
			return [...selectedPaths];
		}
		return [entry.path];
	}

	function onDragStart(e: DragEvent, entry: TreeEntry) {
		const paths = getDraggedPaths(entry);
		draggedItem = entry.path;
		e.dataTransfer?.setData('text/plain', paths.join('\n'));
		e.dataTransfer?.setData('application/x-filebrowser-paths', JSON.stringify(paths));
		if (e.dataTransfer) e.dataTransfer.effectAllowed = 'move';
	}

	/** For a given entry, find the drop-target directory.
	 *  - If the entry IS a directory, target it directly.
	 *  - Otherwise, find its nearest parent expanded directory.
	 *  Returns null if the entry is a root-level file (parent === cwd). */
	function resolveDropTarget(entry: TreeEntry): string | null {
		if (entry.type === 'directory') return entry.path;
		// Walk up to find the nearest expanded parent
		const parentDir = entry.path.substring(0, entry.path.lastIndexOf('/'));
		const cwdNorm = cwd.replace(/\/$/, '');
		if (parentDir === cwdNorm || parentDir === cwd) return null; // root-level file, no folder highlight
		// The parent must be expanded (otherwise the entry wouldn't be visible)
		if (expandedDirs.has(parentDir)) return parentDir;
		return null;
	}

	function onDragOverDir(e: DragEvent, entry: TreeEntry) {
		if (isTabDrag(e)) return;

		// Determine the target folder for this entry
		let targetDir: string | null;
		if (entry.type === 'directory') {
			targetDir = entry.path;
		} else {
			// Non-directory: target the nearest parent expanded folder
			targetDir = resolveDropTarget(entry);
			if (!targetDir) return; // root-level file, let the container dropzone handle it
		}

		// Don't allow dropping onto self or a child of a dragged dir
		if (draggedItem && (targetDir === draggedItem || targetDir.startsWith(draggedItem + '/')))
			return;
		e.preventDefault();
		if (e.dataTransfer) e.dataTransfer.dropEffect = 'move';

		if (dragOverDir !== targetDir) {
			dragOverDir = targetDir;
			// Auto-expand directory after hovering for 600ms (only for actual directories)
			if (dragExpandTimer) clearTimeout(dragExpandTimer);
			if (entry.type === 'directory') {
				dragExpandTimer = setTimeout(() => {
					if (dragOverDir === targetDir && !expandedDirs.has(targetDir!)) {
						toggleDir(targetDir!);
					}
					dragExpandTimer = null;
				}, 600);
			}
		}
	}

	function onDragLeaveDir() {
		if (dragExpandTimer) {
			clearTimeout(dragExpandTimer);
			dragExpandTimer = null;
		}
		dragOverDir = null;
	}

	/** Move one or more paths into a target directory */
	async function moveItemsToDir(paths: string[], targetDir: string) {
		for (const src of paths) {
			// Skip if trying to move into itself or a parent path
			if (src === targetDir || targetDir.startsWith(src + '/')) continue;
			// Skip if already in that directory
			const parentDir = src.substring(0, src.lastIndexOf('/'));
			if (parentDir === targetDir || parentDir === targetDir.replace(/\/$/, '')) continue;
			try {
				await moveFile(src, targetDir);
			} catch {}
		}
		// Refresh current dir + any expanded parents
		fetchDirectory(cwd);
		for (const dir of expandedDirs) {
			fetchSubdir(dir);
		}
		clearSelection();
	}

	async function onDropOnDir(e: DragEvent, entry: TreeEntry) {
		if (isTabDrag(e)) return;

		e.preventDefault();
		if (dragExpandTimer) {
			clearTimeout(dragExpandTimer);
			dragExpandTimer = null;
		}
		dragOverDir = null;

		// Resolve actual target directory (entry itself if dir, or parent expanded dir)
		const targetDir = resolveDropTarget(entry) ?? (entry.type === 'directory' ? entry.path : null);
		if (!targetDir) return; // root-level file drop — container handles it

		// Handle file browser item drag (single or multi)
		if (draggedItem) {
			const rawPaths = e.dataTransfer?.getData('application/x-filebrowser-paths');
			let paths: string[] = [];
			if (rawPaths) {
				try {
					paths = JSON.parse(rawPaths);
				} catch {
					paths = [draggedItem];
				}
			} else {
				paths = [draggedItem];
			}
			await moveItemsToDir(paths, targetDir);
			draggedItem = null;
			return;
		}

		// Handle external file upload
		const files = e.dataTransfer?.files;
		if (files && files.length) {
			await uploadFiles(files, targetDir);
		}
	}

	function onDragEnd() {
		if (dragExpandTimer) {
			clearTimeout(dragExpandTimer);
			dragExpandTimer = null;
		}
		draggedItem = null;
		dragOverDir = null;
		dragOverBreadcrumb = null;
	}

	// ── Breadcrumb drop ────────────────────────────────────────
	function onBreadcrumbDragOver(e: DragEvent, path: string) {
		if (!draggedItem) return;
		e.preventDefault();
		if (e.dataTransfer) e.dataTransfer.dropEffect = 'move';
		dragOverBreadcrumb = path;
	}

	function onBreadcrumbDragLeave() {
		dragOverBreadcrumb = null;
	}

	async function onBreadcrumbDrop(e: DragEvent, path: string) {
		e.preventDefault();
		dragOverBreadcrumb = null;
		if (!draggedItem) return;
		const rawPaths = e.dataTransfer?.getData('application/x-filebrowser-paths');
		let paths: string[] = [];
		if (rawPaths) {
			try {
				paths = JSON.parse(rawPaths);
			} catch {
				paths = [draggedItem];
			}
		} else {
			paths = [draggedItem];
		}
		await moveItemsToDir(paths, path);
		draggedItem = null;
	}

	// ── Drop zone for uploads ───────────────────────────────────
	function onDropzoneOver(e: DragEvent) {
		if (isTabDrag(e)) {
			dropzoneActive = false;
			return;
		}

		e.preventDefault();
		if (draggedItem) {
			// Internal drag — allow drop to move to current directory
			if (e.dataTransfer) e.dataTransfer.dropEffect = 'move';
			return;
		}
		if (e.dataTransfer) e.dataTransfer.dropEffect = 'copy';
		dropzoneActive = true;
	}

	function onDropzoneLeave(e: DragEvent) {
		// Only deactivate if actually leaving the container
		const target = e.relatedTarget as HTMLElement | null;
		if (target && (e.currentTarget as HTMLElement)?.contains(target)) return;
		dropzoneActive = false;
	}

	async function onDropzoneDrop(e: DragEvent) {
		if (isTabDrag(e)) return;

		e.preventDefault();
		dropzoneActive = false;

		// Handle internal drag-and-drop to empty area (move to cwd)
		if (draggedItem) {
			const rawPaths = e.dataTransfer?.getData('application/x-filebrowser-paths');
			let paths: string[] = [];
			if (rawPaths) {
				try {
					paths = JSON.parse(rawPaths);
				} catch {
					paths = [draggedItem];
				}
			} else {
				paths = [draggedItem];
			}
			await moveItemsToDir(paths, cwd);
			draggedItem = null;
			return;
		}

		const files = e.dataTransfer?.files;
		if (files && files.length) {
			await uploadFiles(files, cwd);
		}
	}

	async function uploadFiles(files: FileList, directory: string) {
		for (const file of Array.from(files)) {
			const form = new FormData();
			form.append('file', file);
			form.append('directory', directory);
			try {
				await apiUpload(directory, form);
			} catch {}
		}
		fetchDirectory(cwd);
	}

	function triggerUpload() {
		const input = document.createElement('input');
		input.type = 'file';
		input.multiple = true;
		input.onchange = () => {
			if (input.files) uploadFiles(input.files, cwd);
		};
		input.click();
	}

	// ── New file/folder ─────────────────────────────────────────
	function startNew(type: 'file' | 'folder') {
		showNewInput = type;
		newName = '';
		addMenuOpen = false;
	}

	async function confirmNew() {
		if (!newName.trim() || !showNewInput) return;
		const fullPath = cwd.endsWith('/') ? cwd + newName.trim() : cwd + '/' + newName.trim();
		try {
			await createEntry(fullPath, showNewInput === 'folder' ? 'directory' : 'file');
			fetchDirectory(cwd);
		} catch {}
		showNewInput = null;
		newName = '';
	}

	function cancelNew() {
		showNewInput = null;
		newName = '';
	}

	function toggleAddMenu() {
		addMenuOpen = !addMenuOpen;
	}

	function handleUploadFromMenu() {
		addMenuOpen = false;
		triggerUpload();
	}

	// ── Context menu ───────────────────────────────────────────
	function onContextMenu(e: MouseEvent, entry: TreeEntry) {
		e.preventDefault();
		contextMenu = { x: e.clientX, y: e.clientY, entry };
	}

	function openEntryMenu(e: MouseEvent | KeyboardEvent, entry: TreeEntry) {
		e.stopPropagation();
		contextMenu = { x: 0, y: 0, entry, anchor: e.currentTarget as HTMLElement };
	}

	function closeMenu() {
		contextMenu = null;
	}

	function startRename(entry: TreeEntry) {
		renamingEntry = entry.path;
		renameValue = entry.name;
		closeMenu();
	}

	function copyPath(entry: TreeEntry) {
		navigator.clipboard.writeText(entry.path);
		closeMenu();
	}

	async function confirmRename(entryPath: string) {
		const oldName = entryPath.split('/').pop() ?? '';
		if (!renameValue.trim() || renameValue === oldName) {
			renamingEntry = null;
			return;
		}
		const parentDir = entryPath.substring(0, entryPath.lastIndexOf('/'));
		const dst = parentDir + '/' + renameValue.trim();
		try {
			await moveFile(entryPath, dst);
			fetchDirectory(cwd);
			if (dirContents.has(parentDir)) await fetchSubdir(parentDir);
		} catch {}
		renamingEntry = null;
	}

	async function deleteEntry(entry: TreeEntry) {
		const label = entry.type === 'directory' ? $t('files.folder') : $t('files.file');
		if (!confirm($t('files.deleteEntryConfirm', { type: label, name: entry.name }))) return;
		try {
			await deleteFiles([entry.path]);
			fetchDirectory(cwd);
			refreshParentDir(entry.path);
			// Clean up expand state for deleted directories
			if (entry.type === 'directory') {
				const next = new Set(expandedDirs);
				next.delete(entry.path);
				expandedDirs = next;
				const nextContents = new Map(dirContents);
				nextContents.delete(entry.path);
				dirContents = nextContents;
			}
		} catch {}
		closeMenu();
	}

	function downloadEntry(entry: TreeEntry) {
		const a = document.createElement('a');
		a.href = `/api/workspace/files/download?path=${encodeURIComponent(entry.path)}`;
		a.download = entry.name;
		a.click();
		closeMenu();
	}
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
	class="flex flex-col h-full overflow-hidden relative"
	ondragover={onDropzoneOver}
	ondragleave={onDropzoneLeave}
	ondrop={onDropzoneDrop}
>
	<!-- Header: breadcrumb + actions -->
	<div
		class="flex items-center gap-2 h-9 px-3 border-b border-gray-200 dark:border-white/6 shrink-0"
	>
		<div class="flex items-center gap-1 text-xs min-w-0 flex-1">
			{#each breadcrumbs() as seg, i}
				{#if i > 0}<span class="text-gray-300 dark:text-gray-600">/</span>{/if}
				{#if i === breadcrumbs().length - 1}
					<!-- svelte-ignore a11y_no_static_element_interactions -->
					<span
						class="font-medium truncate transition-colors duration-75
							{dragOverBreadcrumb === seg.path
							? 'text-gray-900 dark:text-white bg-gray-200 dark:bg-white/10 rounded px-1 -mx-1'
							: 'text-gray-900 dark:text-white'}"
						ondragover={(e) => onBreadcrumbDragOver(e, seg.path)}
						ondragleave={onBreadcrumbDragLeave}
						ondrop={(e) => onBreadcrumbDrop(e, seg.path)}>{seg.name}</span
					>
				{:else}
					<!-- svelte-ignore a11y_no_static_element_interactions -->
					<button
						class="shrink-0 transition-colors duration-75
							{dragOverBreadcrumb === seg.path
							? 'text-gray-900 dark:text-white bg-gray-200 dark:bg-white/10 rounded px-1 -mx-1'
							: 'text-gray-500 hover:text-gray-900 dark:hover:text-white'}"
						onclick={() => navigateTo(seg.path)}
						ondragover={(e) => onBreadcrumbDragOver(e, seg.path)}
						ondragleave={onBreadcrumbDragLeave}
						ondrop={(e) => onBreadcrumbDrop(e, seg.path)}>{seg.name}</button
					>
				{/if}
			{/each}
		</div>

		<!-- Refresh -->
		<button
			class="flex items-center justify-center w-5 h-5 rounded text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors duration-100 shrink-0"
			onclick={() => fetchDirectory(cwd)}
			use:tooltip={$t('files.refresh')}
		>
			<Icon name="refresh" size={11} />
		</button>

		<!-- Sort dropdown -->
		<button
			bind:this={sortBtnEl}
			class="flex items-center justify-center w-5 h-5 rounded text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors duration-100 shrink-0"
			onclick={() => {
				sortMenuOpen = !sortMenuOpen;
			}}
			use:tooltip={$t('files.sort')}
		>
			<Icon name="sort" size={11} />
		</button>

		<!-- Three-dot menu -->
		<button
			bind:this={addBtnEl}
			class="flex items-center justify-center w-5 h-5 rounded text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors duration-100 shrink-0"
			onclick={() => {
				toggleAddMenu();
			}}
			use:tooltip={$t('files.actions')}
		>
			<Icon name="three-dots" size={11} />
		</button>
	</div>

	<!-- Ports -->
	{#if workspacePorts.length > 0}
		<div
			class="flex items-center gap-1.5 h-7 px-3 border-b border-gray-200 dark:border-white/6 shrink-0"
		>
			<span class="text-[0.625rem] text-gray-400 shrink-0">{$t('files.ports')}</span>
			{#each workspacePorts as p (p.port)}
				<button
					class="px-1.5 py-0.5 rounded text-[0.6875rem] font-mono font-medium text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-white/6 transition-colors duration-75"
					onclick={() => openPreviewTab(p.port)}
					use:tooltip={$t('files.clickToPreview', { process: p.process })}>:{p.port}</button
				>
			{/each}
		</div>
	{/if}

	<!-- Search -->
	<div
		class="flex items-center gap-1.5 h-8 px-3 border-b border-gray-200 dark:border-white/6 shrink-0"
	>
		<Icon name="search" size={13} class="text-gray-400 shrink-0" />
		<input
			type="text"
			class="flex-1 border-none outline-none bg-transparent text-xs text-gray-900 dark:text-white placeholder:text-gray-400"
			placeholder={$t('files.filter')}
			bind:value={searchQuery}
		/>
		{#if searchQuery}
			<button class="text-gray-400 flex items-center" onclick={() => (searchQuery = '')}>
				<Icon name="xmark" size={11} />
			</button>
		{/if}
	</div>

	<!-- Sort bar replaced with dropdown in toolbar -->

	<!-- File list -->
	<div class="flex-1 overflow-y-auto p-1">
		<!-- New item input -->
		{#if showNewInput}
			<div class="flex items-center gap-2 h-7 px-2">
				<Icon
					name={showNewInput === 'folder' ? 'folder' : 'empty-page'}
					size={14}
					class="text-gray-400 shrink-0"
				/>
				<input
					type="text"
					class="flex-1 border-none outline-none bg-transparent text-xs text-gray-900 dark:text-white"
					placeholder={showNewInput === 'folder'
						? $t('files.folderNamePlaceholder')
						: $t('files.fileNamePlaceholder')}
					bind:value={newName}
					onkeydown={(e) => {
						if (e.key === 'Enter') confirmNew();
						if (e.key === 'Escape') cancelNew();
					}}
					autofocus
				/>
				<button
					class="flex items-center justify-center w-5 h-5 rounded text-green-500 hover:bg-green-50 dark:hover:bg-green-500/10 transition-colors duration-75"
					onclick={confirmNew}
				>
					<Icon name="check" size={12} />
				</button>
				<button
					class="flex items-center justify-center w-5 h-5 rounded text-gray-400 hover:bg-gray-100 dark:hover:bg-white/6 transition-colors duration-75"
					onclick={cancelNew}
				>
					<Icon name="xmark" size={12} />
				</button>
			</div>
		{/if}

		{#if loading && initialLoad}
			<div class="flex items-center justify-center py-12">
				<Spinner size={16} />
			</div>
		{:else if error}
			<div class="flex flex-col items-center justify-center py-12 gap-2">
				<p class="text-xs text-red-400">{error}</p>
				<button
					class="text-xs text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 px-3 py-1 rounded-lg bg-gray-100 dark:bg-white/6 transition-colors duration-100"
					onclick={() => fetchDirectory(cwd)}>{$t('files.retry')}</button
				>
			</div>
		{:else if visibleEntries.length === 0 && !showNewInput}
			<div class="flex items-center justify-center py-12">
				<p class="text-xs text-gray-400 dark:text-gray-600">
					{searchQuery ? $t('files.noMatches') : $t('files.emptyDirectory')}
				</p>
			</div>
		{:else}
			{#each visibleEntries as entry, i (entry.path)}
				{#if renamingEntry === entry.path}
					<!-- Inline rename -->
					<div
						class="flex items-center gap-2 h-7"
						style="padding-left: {8 + entry.depth * 16}px; padding-right: 0.5rem;"
					>
						<Icon
							name={fileIconName(entry.name, entry.type)}
							size={14}
							class="text-gray-400 shrink-0"
						/>
						<input
							type="text"
							class="flex-1 border-none outline-none bg-transparent text-xs text-gray-900 dark:text-white"
							bind:value={renameValue}
							onkeydown={(e) => {
								if (e.key === 'Enter') confirmRename(entry.path);
								if (e.key === 'Escape') renamingEntry = null;
							}}
							onblur={() => confirmRename(entry.path)}
							autofocus
						/>
					</div>
				{:else}
					{@const isSelected = selectedPaths.has(entry.path)}
					{@const isDragTarget =
						dragOverDir !== null &&
						(entry.path === dragOverDir || entry.path.startsWith(dragOverDir + '/'))}
					{@const fileGitStatus = gitStatusForFile(entry)}
					{@const dirGitStatus = gitStatusForDirectory(entry)}
					{@const entryGitStatus = fileGitStatus ?? dirGitStatus}
					{@const entryGitDecoration = entryGitStatus
						? gitStatusDecoration(entryGitStatus.status)
						: null}
					<!-- svelte-ignore a11y_no_static_element_interactions -->
					<button
						class="group flex items-center gap-1 w-full h-7 rounded-lg text-left transition-colors duration-75
							{isSelected
							? 'bg-blue-50 dark:bg-blue-500/10'
							: isDragTarget
								? entry.path === dragOverDir
									? 'bg-blue-100 dark:bg-blue-500/20'
									: 'bg-blue-50/60 dark:bg-blue-500/8'
								: 'hover:bg-gray-100 dark:hover:bg-white/4'}"
						style="padding-left: {8 + entry.depth * 16}px; padding-right: 0.5rem;"
						onclick={(e) => handleClick(e, entry, i)}
						oncontextmenu={(e) => onContextMenu(e, entry)}
						draggable="true"
						ondragstart={(e) => onDragStart(e, entry)}
						ondragover={(e) => onDragOverDir(e, entry)}
						ondragleave={onDragLeaveDir}
						ondrop={(e) => onDropOnDir(e, entry)}
						ondragend={onDragEnd}
					>
						{#if entry.type === 'directory'}
							<!-- svelte-ignore a11y_no_static_element_interactions -->
							<span
								class="flex items-center justify-center w-4 shrink-0 text-gray-400 dark:text-gray-600 hover:text-gray-600 dark:hover:text-gray-400 cursor-pointer"
								role="button"
								tabindex="-1"
								onclick={(e) => {
									e.stopPropagation();
									toggleDir(entry.path);
								}}
								onkeydown={(e) => {
									if (e.key === 'Enter') {
										e.stopPropagation();
										toggleDir(entry.path);
									}
								}}
							>
								<Icon
									name={expandedDirs.has(entry.path) ? 'chevron-down' : 'chevron-right'}
									size={10}
								/>
							</span>
						{:else}
							<span class="w-4 shrink-0"></span>
						{/if}
						<span
							class="flex items-center justify-center w-4 shrink-0 {entry.type === 'directory'
								? 'text-gray-500 dark:text-gray-400'
								: 'text-gray-400 dark:text-gray-500'}"
						>
							<Icon name={fileIconName(entry.name, entry.type)} size={14} strokeWidth={1.4} />
						</span>
						{#if entry.type === 'directory'}
							<span
								class="flex-1 text-xs truncate {entryGitDecoration
									? entryGitDecoration.nameColor
									: 'text-gray-800 dark:text-gray-200'}">{entry.name}</span
							>
						{:else}
							<span
								class="flex-1 text-xs truncate {entryGitDecoration
									? entryGitDecoration.nameColor
									: 'text-gray-800 dark:text-gray-200'}">{entry.name}</span
							>
						{/if}
						{#if dirGitStatus && entryGitDecoration}
							<span
								class="w-1.5 h-1.5 rounded-full shrink-0 {entryGitDecoration.markerColor}"
								use:tooltip={gitStatusTooltip(dirGitStatus, entry)}
							></span>
						{/if}
						{#if fileGitStatus && entryGitDecoration}
							<span
								class="text-[0.625rem] font-mono font-bold shrink-0 {entryGitDecoration.badgeColor}"
								use:tooltip={gitStatusTooltip(fileGitStatus, entry)}>{entryGitDecoration.char}</span
							>
						{/if}
						{#if entry.type !== 'directory' && entry.size !== null}
							<span
								class="ml-1 text-[0.6875rem] font-mono text-gray-400 dark:text-gray-600 shrink-0"
								>{formatSize(entry.size)}</span
							>
						{/if}
						<!-- Three-dot menu per entry -->
						<span
							class="flex items-center justify-center w-5 h-5 rounded shrink-0 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-200 dark:hover:bg-white/10 transition-all duration-75"
							role="button"
							tabindex="-1"
							onclick={(e) => openEntryMenu(e, entry)}
							onkeydown={(e) => {
								if (e.key === 'Enter') openEntryMenu(e, entry);
							}}
							aria-label={$t('files.moreActions')}
						>
							<Icon name="three-dots" size={12} />
						</span>
					</button>
				{/if}
			{/each}
		{/if}
	</div>

	<!-- Upload dropzone overlay -->
	{#if dropzoneActive}
		<div
			class="absolute inset-0 bg-blue-500/10 border-2 border-dashed border-blue-400 dark:border-blue-500 rounded-lg flex items-center justify-center z-10 pointer-events-none"
		>
			<p class="text-xs font-medium text-blue-500 dark:text-blue-400">{$t('files.dropToUpload')}</p>
		</div>
	{/if}

	<!-- Multi-select action bar -->
	{#if selectedPaths.size > 0}
		<div
			class="flex items-center justify-between h-8 px-2 border-t border-gray-200 dark:border-white/6 shrink-0 bg-blue-50 dark:bg-blue-500/5"
		>
			<span class="text-[0.6875rem] font-medium text-blue-600 dark:text-blue-400"
				>{$t('files.selected', { count: selectedPaths.size })}</span
			>
			<div class="flex items-center gap-1">
				<button
					class="text-[0.6875rem] px-2 py-0.5 rounded text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 hover:bg-gray-200 dark:hover:bg-white/10 transition-colors duration-75"
					onclick={selectAll}>{$t('files.all')}</button
				>
				<button
					class="text-[0.6875rem] px-2 py-0.5 rounded text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 hover:bg-gray-200 dark:hover:bg-white/10 transition-colors duration-75"
					onclick={archiveSelected}
					use:tooltip={$t('files.downloadAsZip')}><Icon name="download" size={12} /></button
				>
				<button
					class="text-[0.6875rem] px-2 py-0.5 rounded text-red-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10 transition-colors duration-75"
					onclick={deleteSelected}
					use:tooltip={$t('files.deleteSelected')}><Icon name="trash" size={12} /></button
				>
				<button
					class="text-[0.6875rem] px-2 py-0.5 rounded text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors duration-75"
					onclick={clearSelection}><Icon name="xmark" size={11} /></button
				>
			</div>
		</div>
	{/if}
</div>

{#if sortMenuOpen && sortBtnEl}
	<DropdownMenu
		anchor={sortBtnEl}
		items={[
			{
				label: $t('files.name'),
				icon: sortBy === 'name' ? (sortDir === 'asc' ? 'chevron-up' : 'chevron-down') : undefined,
				active: sortBy === 'name',
				onclick: () => toggleSort('name')
			},
			{
				label: $t('files.size'),
				icon: sortBy === 'size' ? (sortDir === 'asc' ? 'chevron-up' : 'chevron-down') : undefined,
				active: sortBy === 'size',
				onclick: () => toggleSort('size')
			},
			{
				label: $t('files.date'),
				icon:
					sortBy === 'modified' ? (sortDir === 'asc' ? 'chevron-up' : 'chevron-down') : undefined,
				active: sortBy === 'modified',
				onclick: () => toggleSort('modified')
			}
		]}
		onclose={() => (sortMenuOpen = false)}
	/>
{/if}

{#if addMenuOpen && addBtnEl}
	<DropdownMenu
		anchor={addBtnEl}
		items={[
			{ label: $t('files.newFile'), icon: 'plus', onclick: () => startNew('file') },
			{ label: $t('files.newFolder'), icon: 'folder', onclick: () => startNew('folder') },
			{ label: '', divider: true, onclick: () => {} },
			{ label: $t('files.uploadFile'), icon: 'upload', onclick: () => handleUploadFromMenu() },
			{ label: '', divider: true, onclick: () => {} },
			{
				label: showHidden ? $t('files.hideHidden') : $t('files.showHidden'),
				icon: 'eye',
				onclick: () => toggleHidden()
			}
		]}
		onclose={() => (addMenuOpen = false)}
	/>
{/if}

{#if contextMenu}
	<DropdownMenu
		anchor={contextMenu.anchor ?? { x: contextMenu.x, y: contextMenu.y }}
		items={[
			...(contextMenu.entry.type === 'directory'
				? [
						{
							label: $t('files.openFolder'),
							icon: 'folder',
							onclick: () => {
								setFileBrowserCwd(contextMenu!.entry.path);
								closeMenu();
							}
						},
						{
							label: expandedDirs.has(contextMenu.entry.path)
								? $t('files.collapse')
								: $t('files.expand'),
							icon: expandedDirs.has(contextMenu.entry.path) ? 'chevron-down' : 'chevron-right',
							onclick: () => {
								toggleDir(contextMenu!.entry.path);
								closeMenu();
							}
						},
						{ label: '', divider: true, onclick: () => {} }
					]
				: []),
			{ label: $t('files.copyPath'), icon: 'copy', onclick: () => copyPath(contextMenu!.entry) },
			{ label: $t('files.rename'), icon: 'pencil', onclick: () => startRename(contextMenu!.entry) },
			...(contextMenu.entry.type !== 'directory'
				? [
						{
							label: $t('files.download'),
							icon: 'download',
							onclick: () => downloadEntry(contextMenu!.entry)
						}
					]
				: []),
			{ label: $t('files.delete'), icon: 'xmark', onclick: () => deleteEntry(contextMenu!.entry) }
		]}
		onclose={closeMenu}
	/>
{/if}
