<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { fetchHandler } from '$lib/apis';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import { t } from '$lib/i18n';

	interface Props {
		src: string;
	}

	let { src }: Props = $props();

	let loading = $state(true);
	let error = $state('');
	let db: any = null;
	let tables = $state<string[]>([]);
	let activeTable = $state('');
	let columns = $state<string[]>([]);
	let rows = $state<any[][]>([]);
	let totalRows = $state(0);
	let page = $state(0);
	let queryMode = $state(false);
	let customQuery = $state('');
	let queryError = $state('');
	const PAGE_SIZE = 100;

	async function loadDb() {
		loading = true;
		error = '';
		try {
			const initSqlJs = (await import('sql.js')).default;
			const SQL = await initSqlJs({
				locateFile: () => `/sql-wasm.wasm`
			});

			const res = await fetchHandler(src);
			if (!res.ok) throw new Error(`HTTP ${res.status}`);
			const buf = await res.arrayBuffer();
			db = new SQL.Database(new Uint8Array(buf));

			// Get table names
			const result = db.exec("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name");
			if (result.length > 0) {
				tables = result[0].values.map((r: any[]) => r[0] as string);
				if (tables.length > 0) {
					selectTable(tables[0]);
				}
			}
		} catch (e: any) {
			console.error('SQLite load error:', e);
			error = e.message || $t('sqlite.loadError');
		} finally {
			loading = false;
		}
	}

	function selectTable(name: string) {
		activeTable = name;
		page = 0;
		queryMode = false;
		queryError = '';

		// Get total row count
		try {
			const countResult = db.exec(`SELECT COUNT(*) FROM "${name}"`);
			totalRows = (countResult[0]?.values[0]?.[0] as number) ?? 0;
		} catch {
			totalRows = 0;
		}

		fetchPage();
	}

	function fetchPage() {
		if (!db || !activeTable) return;
		try {
			const offset = page * PAGE_SIZE;
			const result = db.exec(`SELECT * FROM "${activeTable}" LIMIT ${PAGE_SIZE} OFFSET ${offset}`);
			if (result.length > 0) {
				columns = result[0].columns;
				rows = result[0].values;
			} else {
				columns = [];
				rows = [];
			}
		} catch (e: any) {
			queryError = e.message;
		}
	}

	function runQuery() {
		if (!db || !customQuery.trim()) return;
		queryError = '';
		try {
			const result = db.exec(customQuery.trim());
			if (result.length > 0) {
				columns = result[0].columns;
				rows = result[0].values;
				totalRows = rows.length;
			} else {
				columns = [];
				rows = [];
				totalRows = 0;
			}
			page = 0;
		} catch (e: any) {
			queryError = e.message;
		}
	}

	function nextPage() {
		if ((page + 1) * PAGE_SIZE < totalRows) {
			page++;
			fetchPage();
		}
	}

	function prevPage() {
		if (page > 0) {
			page--;
			fetchPage();
		}
	}

	function formatCell(val: unknown): string {
		if (val === null) return $t('sqlite.null');
		if (val instanceof Uint8Array) return $t('sqlite.blob', { size: val.length });
		return String(val);
	}

	function cellClass(val: unknown): string {
		if (val === null) return 'cell-null';
		if (val instanceof Uint8Array) return 'cell-blob';
		if (typeof val === 'number') return 'cell-number';
		return '';
	}

	onMount(() => {
		loadDb();
	});

	onDestroy(() => {
		if (db) {
			db.close();
			db = null;
		}
	});
</script>

<div class="sqlite-view">
	{#if loading}
		<div class="state"><Spinner size={20} /></div>
	{:else if error}
		<div class="state error-msg">{error}</div>
	{:else}
		<!-- Table tabs -->
		<div class="tab-bar">
			<div class="tabs">
				{#each tables as table}
					<button
						class="tab"
						class:active={activeTable === table && !queryMode}
						onclick={() => selectTable(table)}>{table}</button
					>
				{/each}
			</div>
			<button
				class="tab query-tab"
				class:active={queryMode}
				onclick={() => {
					queryMode = true;
				}}>{$t('sqlite.sql')}</button
			>
		</div>

		<!-- Query input -->
		{#if queryMode}
			<div class="query-bar">
				<textarea
					class="query-input"
					bind:value={customQuery}
					placeholder={$t('sqlite.queryPlaceholder')}
					rows="2"
					onkeydown={(e) => {
						if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') runQuery();
					}}
				></textarea>
				<button class="run-btn" onclick={runQuery}>{$t('sqlite.run')}</button>
			</div>
		{/if}

		{#if queryError}
			<div class="query-error">{queryError}</div>
		{/if}

		<!-- Results table -->
		<div class="table-scroll">
			<table>
				<thead>
					<tr>
						<th class="row-num">#</th>
						{#each columns as col}
							<th>{col}</th>
						{/each}
					</tr>
				</thead>
				<tbody>
					{#each rows as row, i}
						<tr>
							<td class="row-num">{page * PAGE_SIZE + i + 1}</td>
							{#each row as cell}
								<td class={cellClass(cell)}>{formatCell(cell)}</td>
							{/each}
						</tr>
					{/each}
				</tbody>
			</table>
		</div>

		<!-- Pagination -->
		{#if !queryMode && totalRows > PAGE_SIZE}
			<div class="pagination">
				<button class="page-btn" onclick={prevPage} disabled={page === 0}
					>{$t('sqlite.prev')}</button
				>
				<span class="page-info">
					{$t('sqlite.pageInfo', {
						start: page * PAGE_SIZE + 1,
						end: Math.min((page + 1) * PAGE_SIZE, totalRows),
						total: totalRows
					})}
				</span>
				<button class="page-btn" onclick={nextPage} disabled={(page + 1) * PAGE_SIZE >= totalRows}
					>{$t('sqlite.next')}</button
				>
			</div>
		{/if}
	{/if}
</div>

<style>
	@reference "../../../app.css";

	.sqlite-view {
		display: flex;
		flex-direction: column;
		height: 100%;
		overflow: hidden;
	}

	.state {
		display: flex;
		align-items: center;
		justify-content: center;
		height: 100%;
	}

	.error-msg {
		font-size: 0.8125rem;
		color: #ef4444;
	}

	/* ── Tab bar ──────────────────────────────────── */

	.tab-bar {
		display: flex;
		align-items: center;
		gap: 0;
		border-bottom: 1px solid var(--app-border);
		padding: 0 0.25rem;
		flex-shrink: 0;
		overflow-x: auto;
	}

	.tabs {
		display: flex;
		gap: 0;
		flex: 1;
		min-width: 0;
		overflow-x: auto;
	}

	.tab {
		padding: 0.375rem 0.75rem;
		font-size: 0.6875rem;
		font-weight: 500;
		color: var(--app-fg-muted);
		border-bottom: 0.125rem solid transparent;
		transition: all 0.1s;
		white-space: nowrap;
	}

	.tab:hover {
		color: var(--app-fg);
	}

	.tab.active {
		color: var(--app-fg);
		border-bottom-color: var(--app-fg);
	}

	.query-tab {
		margin-left: auto;
		font-family: var(--font-mono);
		font-size: 0.625rem;
	}

	/* ── Query bar ────────────────────────────────── */

	.query-bar {
		display: flex;
		gap: 0.5rem;
		padding: 0.5rem 0.75rem;
		border-bottom: 1px solid var(--app-divider);
		flex-shrink: 0;
	}

	.query-input {
		flex: 1;
		font-family: var(--font-mono);
		font-size: 0.75rem;
		padding: 0.375rem 0.625rem;
		border: 1px solid var(--app-border);
		border-radius: 0.375rem;
		background: transparent;
		color: var(--app-fg);
		resize: vertical;
		outline: none;
	}

	.query-input:focus {
		border-color: var(--app-fg);
	}

	.run-btn {
		padding: 0.375rem 0.75rem;
		font-size: 0.6875rem;
		font-weight: 500;
		color: var(--app-bg);
		background: var(--app-fg);
		border-radius: 0.375rem;
		align-self: flex-end;
		transition: background 0.1s;
	}

	.run-btn:hover {
		background: var(--app-fg-muted);
	}

	.query-error {
		padding: 0.375rem 0.75rem;
		font-size: 0.6875rem;
		font-family: var(--font-mono);
		color: #ef4444;
		background: rgba(239, 68, 68, 0.06);
		white-space: pre-wrap;
	}

	/* ── Table ────────────────────────────────────── */

	.table-scroll {
		flex: 1;
		overflow: auto;
	}

	table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.75rem;
		font-family: var(--font-mono);
		white-space: nowrap;
	}

	thead {
		position: sticky;
		top: 0;
		z-index: 2;
	}

	th {
		background: var(--app-hover);
		color: var(--app-fg-muted);
		font-weight: 600;
		font-size: 0.6875rem;
		padding: 0.3125rem 0.625rem;
		text-align: left;
		border-bottom: 1px solid var(--app-border);
	}

	td {
		padding: 0.1875rem 0.625rem;
		color: var(--app-fg);
		border-bottom: 1px solid var(--app-divider);
	}

	tbody tr:hover td {
		background: var(--app-hover);
	}

	.row-num {
		color: var(--app-fg-subtle);
		font-size: 0.625rem;
		text-align: right;
		padding-right: 0.375rem;
		user-select: none;
		min-width: 2rem;
		border-right: 1px solid var(--app-divider);
	}

	.cell-null {
		color: var(--app-fg-subtle);
		font-style: italic;
	}

	.cell-blob {
		color: var(--app-fg-subtle);
		font-style: italic;
	}

	.cell-number {
		color: #d97706;
	}

	:global(.dark) .cell-number {
		color: #fbbf24;
	}

	/* ── Pagination ───────────────────────────────── */

	.pagination {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.75rem;
		padding: 0.375rem;
		border-top: 1px solid var(--app-divider);
		flex-shrink: 0;
	}

	.page-btn {
		font-size: 0.6875rem;
		padding: 0.1875rem 0.625rem;
		border-radius: 0.25rem;
		color: var(--app-fg-muted);
		transition: all 0.1s;
	}

	.page-btn:hover:not(:disabled) {
		background: var(--app-hover);
		color: var(--app-fg);
	}

	.page-btn:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}

	.page-info {
		font-size: 0.6875rem;
		color: var(--app-fg-subtle);
		font-variant-numeric: tabular-nums;
	}
</style>
