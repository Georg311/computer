<script lang="ts">
	import { activeWorkspace, openFileTab, gitReviewOpen } from '$lib/stores';
	import { getGitDiff } from '$lib/apis/git';
	import { gitStatusStore, type GitStatus, type GitFile } from '$lib/stores/gitStatus.svelte';

	import { tooltip } from '$lib/tooltip';
	import { t } from '$lib/i18n';
	import Icon from './Icon.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';

	type DiffLine = { type: 'added' | 'removed' | 'context'; content: string };
	type DiffHunk = { header: string; lines: DiffLine[] };
	type DiffFile = { path: string; hunks: DiffHunk[] };
	type ReviewFile = {
		key: string;
		path: string;
		status: string;
		staged: boolean;
		diffFiles: DiffFile[];
		additions: number;
		deletions: number;
		expanded: boolean;
	};
	type NumberedLine = DiffLine & { oldNumber: number | null; newNumber: number | null };

	let gitStatus = $derived(gitStatusStore.status);
	let reviewFiles = $state<ReviewFile[]>([]);
	let loading = $state(false);
	let refreshing = $state(false);
	let error = $state('');
	let loadSeq = 0;

	const workspacePath = $derived($activeWorkspace?.path ?? '');
	const totalChanges = $derived(reviewFiles.length);
	const anyExpanded = $derived(reviewFiles.some((file) => file.expanded));

	// React to git status changes from centralized store
	let _prevStatusRef: GitStatus | null = null;
	$effect(() => {
		const status = gitStatus;
		if (!workspacePath || !status) {
			reviewFiles = [];
			return;
		}
		// Only re-fetch diffs when status actually changes
		if (status !== _prevStatusRef) {
			const isInitial = _prevStatusRef === null;
			_prevStatusRef = status;
			fetchDiffs(status, isInitial);
		}
	});

	async function fetchDiffs(status: GitStatus, initial = false) {
		const seq = ++loadSeq;
		const root = workspacePath;
		if (!root) return;

		if (initial) loading = true;
		else refreshing = true;
		error = '';

		try {
			if (!status.is_repo) {
				reviewFiles = [];
				return;
			}

			const previousExpansion = new Map(reviewFiles.map((file) => [file.key, file.expanded]));
			const nextFiles = await Promise.all(
				(status.files ?? []).map(async (file) => {
					const params = new URLSearchParams({
						root,
						file: file.path,
						staged: String(file.staged)
					});
					if (file.status === 'untracked') params.set('untracked', 'true');

					let diffFiles: DiffFile[] = [];
					try {
						const diff = (await getGitDiff(params.toString())) as { files?: DiffFile[] };
						diffFiles = diff.files ?? [];
					} catch {
						diffFiles = [];
					}

					const counts = countDiff(diffFiles);
					const key = fileKey(file);
					return {
						key,
						path: file.path,
						status: file.status,
						staged: file.staged,
						diffFiles,
						additions: counts.additions,
						deletions: counts.deletions,
						expanded: previousExpansion.get(key) ?? true
					};
				})
			);

			if (seq !== loadSeq || root !== workspacePath) return;
			reviewFiles = nextFiles;
		} catch (e) {
			if (seq !== loadSeq) return;
			error = e instanceof Error ? e.message : 'Failed to load git changes';
			reviewFiles = [];
		} finally {
			if (seq === loadSeq) {
				loading = false;
				refreshing = false;
			}
		}
	}

	async function refreshReview(initial = false) {
		await gitStatusStore.refresh({ force: true });
	}

	function fileKey(file: GitFile): string {
		return `${file.staged ? 'staged' : 'unstaged'}:${file.status}:${file.path}`;
	}

	function countDiff(files: DiffFile[]): { additions: number; deletions: number } {
		let additions = 0;
		let deletions = 0;
		for (const file of files) {
			for (const hunk of file.hunks) {
				for (const line of hunk.lines) {
					if (line.type === 'added') additions += 1;
					if (line.type === 'removed') deletions += 1;
				}
			}
		}
		return { additions, deletions };
	}

	function toggleFile(key: string) {
		reviewFiles = reviewFiles.map((file) =>
			file.key === key ? { ...file, expanded: !file.expanded } : file
		);
	}

	function toggleAll() {
		const expand = !anyExpanded;
		reviewFiles = reviewFiles.map((file) => ({ ...file, expanded: expand }));
	}

	function openFile(path: string) {
		const fullPath = workspacePath.replace(/\/$/, '') + '/' + path;
		openFileTab(fullPath);
		gitReviewOpen.set(false);
	}

	function pathParts(path: string): { dir: string; name: string } {
		const slash = path.lastIndexOf('/');
		if (slash < 0) return { dir: '', name: path };
		return { dir: path.slice(0, slash + 1), name: path.slice(slash + 1) };
	}

	function statusMeta(status: string): { char: string; label: string; className: string } {
		switch (status) {
			case 'added':
				return { char: 'A', label: 'Added', className: 'text-green-600 dark:text-green-400' };
			case 'untracked':
				return { char: 'U', label: 'Untracked', className: 'text-green-600 dark:text-green-400' };
			case 'modified':
				return { char: 'M', label: 'Modified', className: 'text-amber-500 dark:text-amber-400' };
			case 'deleted':
				return { char: 'D', label: 'Deleted', className: 'text-red-500 dark:text-red-400' };
			case 'renamed':
				return { char: 'R', label: 'Renamed', className: 'text-blue-500 dark:text-blue-400' };
			case 'copied':
				return { char: 'C', label: 'Copied', className: 'text-blue-500 dark:text-blue-400' };
			case 'conflict':
				return { char: '!', label: 'Conflict', className: 'text-orange-500 dark:text-orange-400' };
			default:
				return { char: '?', label: status, className: 'text-gray-400 dark:text-gray-500' };
		}
	}

	function hunkStart(header: string): { oldStart: number; newStart: number } {
		const match = header.match(/^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/);
		return {
			oldStart: match ? Number(match[1]) : 0,
			newStart: match ? Number(match[2]) : 0
		};
	}

	function numberedLines(hunk: DiffHunk): NumberedLine[] {
		let { oldStart, newStart } = hunkStart(hunk.header);

		return hunk.lines.map((line) => {
			if (line.type === 'added') {
				return { ...line, oldNumber: null, newNumber: newStart++ };
			}
			if (line.type === 'removed') {
				return { ...line, oldNumber: oldStart++, newNumber: null };
			}
			return { ...line, oldNumber: oldStart++, newNumber: newStart++ };
		});
	}

	function blockClass(type: DiffLine['type']): string {
		switch (type) {
			case 'added':
				return 'bg-green-100 border-l-[0.1875rem] border-l-green-500 dark:bg-green-500/15 dark:border-l-green-400';
			case 'removed':
				return 'bg-red-100 diff-gutter-removed dark:bg-red-500/15';
			default:
				return '';
		}
	}

	function textClass(type: DiffLine['type']): string {
		switch (type) {
			case 'added':
				return 'text-green-900 dark:text-green-300';
			case 'removed':
				return 'text-red-900 dark:text-red-300';
			default:
				return 'text-gray-600 dark:text-gray-400';
		}
	}

	function prefixClass(type: DiffLine['type']): string {
		switch (type) {
			case 'added':
				return 'text-green-600 dark:text-green-400';
			case 'removed':
				return 'text-red-500 dark:text-red-400';
			default:
				return 'text-gray-400 dark:text-gray-600';
		}
	}

	function linePrefix(type: DiffLine['type']): string {
		if (type === 'added') return '+';
		if (type === 'removed') return '-';
		return ' ';
	}

	type LineGroup = { type: DiffLine['type']; lines: NumberedLine[] };

	function groupLines(lines: NumberedLine[]): LineGroup[] {
		const groups: LineGroup[] = [];
		for (const line of lines) {
			const last = groups[groups.length - 1];
			if (last && last.type === line.type) {
				last.lines.push(line);
			} else {
				groups.push({ type: line.type, lines: [line] });
			}
		}
		return groups;
	}
</script>

<div
	class="flex h-full flex-col overflow-hidden bg-white text-gray-900 dark:bg-black dark:text-gray-100"
>
	{#if loading && !gitStatus}
		<div class="flex h-full items-center justify-center">
			<Spinner size={16} />
		</div>
	{:else if error && !gitStatus}
		<div class="flex h-full flex-col items-center justify-center gap-2 px-6 text-center">
			<Icon name="git-diff" size={24} class="text-gray-300 dark:text-gray-700" />
			<p class="text-xs font-medium text-gray-700 dark:text-gray-300">Unable to load changes</p>
			<p class="max-w-sm text-[0.6875rem] text-gray-400 dark:text-gray-600">{error}</p>
		</div>
	{:else if !gitStatus?.is_repo}
		<div class="flex h-full flex-col items-center justify-center gap-2 px-6 text-center">
			<Icon name="git-branch" size={24} class="text-gray-300 dark:text-gray-700" />
			<p class="text-xs text-gray-400 dark:text-gray-600">Not a git repository</p>
		</div>
	{:else}
		<header
			class="flex h-9 shrink-0 items-center gap-2 border-b border-gray-200 px-3 dark:border-white/6"
		>
			<div class="flex min-w-0 flex-1 items-center gap-1.5">
				<Icon name="git-branch" size={14} class="shrink-0 text-gray-400 dark:text-gray-600" />
				<span class="truncate font-mono text-xs font-medium text-gray-700 dark:text-gray-300"
					>{gitStatus.branch || 'HEAD'}</span
				>
				{#if gitStatus.upstream}
					<Icon name="chevron-right" size={12} class="shrink-0 text-gray-300 dark:text-gray-700" />
					<span class="truncate font-mono text-[0.6875rem] text-gray-400 dark:text-gray-600"
						>{gitStatus.upstream}</span
					>
				{/if}
				{#if gitStatus.ahead > 0}
					<span class="font-mono text-[0.625rem] text-gray-400 dark:text-gray-600"
						>+{gitStatus.ahead}</span
					>
				{/if}
				{#if gitStatus.behind > 0}
					<span class="font-mono text-[0.625rem] text-gray-400 dark:text-gray-600"
						>-{gitStatus.behind}</span
					>
				{/if}
				{#if totalChanges > 0}
					<span class="ml-1 font-mono text-[0.625rem] text-gray-400 dark:text-gray-600"
						>{totalChanges} changed</span
					>
				{/if}
			</div>

			<button
				class="flex h-6 w-6 items-center justify-center rounded-md text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-white/6 dark:hover:text-gray-300"
				onclick={() => refreshReview(false)}
				disabled={refreshing}
				aria-label={$t('a11y.refreshChanges')}
				use:tooltip={$t('a11y.refreshChanges')}
			>
				<Icon name="refresh" size={12} class={refreshing ? 'animate-spin' : ''} />
			</button>
		</header>

		{#if totalChanges > 0}
			<div
				class="flex h-8 shrink-0 items-center gap-2 border-b border-gray-200 px-3 dark:border-white/6"
			>
				<button
					class="flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[0.6875rem] text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-white/6 dark:hover:text-gray-300"
					onclick={toggleAll}
				>
					<Icon name={anyExpanded ? 'chevron-down' : 'chevron-right'} size={12} />
					<span>{anyExpanded ? 'Collapse All' : 'Expand All'}</span>
				</button>
				<span class="text-[0.6875rem] text-gray-500 dark:text-gray-400">Uncommitted</span>
				<span class="ml-auto text-[0.6875rem] text-gray-400 dark:text-gray-600"
					>{totalChanges} {totalChanges === 1 ? 'change' : 'changes'}</span
				>
			</div>
		{/if}

		<div class="min-h-0 flex-1 overflow-y-auto">
			{#if totalChanges === 0}
				<div class="flex h-full items-center justify-center px-6">
					<div class="flex -translate-y-8 flex-col items-center gap-2 text-center">
						<Icon
							name="git-diff"
							size={30}
							strokeWidth={1.2}
							class="text-gray-300 dark:text-gray-700"
						/>
						<h2 class="text-sm font-medium text-gray-700 dark:text-gray-300">
							No file changes yet
						</h2>
						<p class="text-xs text-gray-400 dark:text-gray-600">
							Changes in this project will appear here.
						</p>
					</div>
				</div>
			{:else}
				<div class="p-1">
					{#each reviewFiles as file (file.key)}
						{@const parts = pathParts(file.path)}
						{@const meta = statusMeta(file.status)}
						<section class="overflow-hidden rounded-lg">
							<button
								class="flex h-8 w-full min-w-0 items-center gap-1.5 rounded-lg px-2 text-left transition-colors hover:bg-gray-100 dark:hover:bg-white/4"
								onclick={() => toggleFile(file.key)}
							>
								<Icon
									name="chevron-right"
									size={12}
									class="shrink-0 text-gray-400 transition-transform dark:text-gray-600 {file.expanded
										? 'rotate-90'
										: ''}"
								/>
								<span
									class="w-4 shrink-0 text-center font-mono text-[0.6875rem] font-bold {meta.className}"
									title={meta.label}>{meta.char}</span
								>
								<Icon name="git-diff" size={13} class="shrink-0 text-gray-400 dark:text-gray-600" />
								<div class="flex min-w-0 flex-1 items-baseline gap-2">
									<!-- svelte-ignore a11y_no_static_element_interactions -->
									<span
										class="truncate text-xs font-medium text-gray-800 dark:text-gray-200 hover:underline"
										onclick={(e) => {
											e.stopPropagation();
											openFile(file.path);
										}}>{parts.name}</span
									>
									{#if parts.dir}
										<span
											class="hidden truncate text-[0.6875rem] text-gray-400 dark:text-gray-600 sm:inline"
											>{parts.dir}</span
										>
									{/if}
								</div>
								{#if file.additions > 0}
									<span
										class="shrink-0 font-mono text-[0.6875rem] font-medium text-green-600 dark:text-green-400"
										>+{file.additions}</span
									>
								{/if}
								{#if file.deletions > 0}
									<span
										class="shrink-0 font-mono text-[0.6875rem] font-medium text-red-500 dark:text-red-400"
										>-{file.deletions}</span
									>
								{/if}

								<span
									class="shrink-0 rounded px-1.5 py-0.5 text-[0.625rem] font-medium text-rose-500 bg-rose-50 dark:bg-rose-500/10 dark:text-rose-300"
								>
									{file.staged ? 'Staged' : 'Uncommitted'}
								</span>
							</button>

							{#if file.expanded}
								<div
									class="mb-1 overflow-x-auto border-y border-gray-100 bg-white font-mono text-[0.6875rem] leading-[1.125rem] dark:border-white/4 dark:bg-black"
								>
									<div class="diff-content">
										{#if file.diffFiles.some((diffFile) => diffFile.hunks.length > 0)}
											{#each file.diffFiles as diffFile}
												{#if file.diffFiles.length > 1}
													<div
														class="sticky top-0 z-10 border-b border-gray-100 bg-gray-50 px-2 py-1 text-[0.625rem] font-medium text-gray-500 dark:border-white/4 dark:bg-white/3 dark:text-gray-400"
													>
														{diffFile.path}
													</div>
												{/if}
												{#each diffFile.hunks as hunk}
													<div
														class="grid w-full grid-cols-[2.75rem_2.75rem_1.25rem_auto] border-b border-gray-100 bg-gray-50 text-gray-400 dark:border-white/4 dark:bg-white/3 dark:text-gray-600"
													>
														<span></span>
														<span></span>
														<span></span>
														<code class="whitespace-pre px-2 py-0.5">{hunk.header}</code>
													</div>
													{#each groupLines(numberedLines(hunk)) as group}
														<div class="w-full {blockClass(group.type)}">
															{#each group.lines as line}
																<div class="grid w-full grid-cols-[2.75rem_2.75rem_1.25rem_auto]">
																	<span
																		class="select-none border-r border-black/5 px-2 text-right text-gray-400 dark:border-white/4 dark:text-gray-600"
																		>{line.oldNumber ?? ''}</span
																	>
																	<span
																		class="select-none border-r border-black/5 px-2 text-right text-gray-400 dark:border-white/4 dark:text-gray-600"
																		>{line.newNumber ?? ''}</span
																	>
																	<span
																		class="select-none px-1 text-center {prefixClass(line.type)}"
																		>{linePrefix(line.type)}</span
																	>
																	<code class="whitespace-pre px-2 {textClass(line.type)}"
																		>{line.content || ' '}</code
																	>
																</div>
															{/each}
														</div>
													{/each}
												{/each}
											{/each}
										{:else}
											<div
												class="px-3 py-8 text-center text-[0.6875rem] text-gray-400 dark:text-gray-600"
											>
												No textual diff available
											</div>
										{/if}
									</div>
								</div>
							{/if}
						</section>
					{/each}
				</div>
			{/if}
		</div>
	{/if}
</div>

<style>
	.diff-content {
		width: max-content;
		min-width: 100%;
	}

	.diff-gutter-removed {
		border-left: 0.1875rem solid transparent;
		border-image: repeating-linear-gradient(
				-45deg,
				#ef4444 0,
				#ef4444 1px,
				transparent 1px,
				transparent 0.1875rem
			)
			3;
	}
</style>
