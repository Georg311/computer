<script lang="ts">
	interface Props {
		data: unknown;
		key?: string;
		depth?: number;
		maxExpandDepth?: number;
	}

	let { data, key = '', depth = 0, maxExpandDepth = 2 }: Props = $props();

	let expanded = $state(depth < maxExpandDepth);

	let isObject = $derived(data !== null && typeof data === 'object' && !Array.isArray(data));
	let isArray = $derived(Array.isArray(data));
	let isExpandable = $derived(isObject || isArray);

	let entries = $derived(() => {
		if (isObject) return Object.entries(data as Record<string, unknown>);
		if (isArray) return (data as unknown[]).map((v, i) => [String(i), v] as [string, unknown]);
		return [];
	});

	let previewText = $derived(() => {
		if (isObject) {
			const keys = Object.keys(data as Record<string, unknown>);
			return `{${keys.length}}`;
		}
		if (isArray) {
			return `[${(data as unknown[]).length}]`;
		}
		return '';
	});

	function toggle() {
		expanded = !expanded;
	}

	function formatValue(val: unknown): { text: string; className: string } {
		if (val === null) return { text: 'null', className: 'val-null' };
		if (val === undefined) return { text: 'undefined', className: 'val-null' };
		if (typeof val === 'boolean') return { text: String(val), className: 'val-bool' };
		if (typeof val === 'number') return { text: String(val), className: 'val-number' };
		if (typeof val === 'string') return { text: `"${val}"`, className: 'val-string' };
		return { text: String(val), className: 'val-null' };
	}
</script>

{#if isExpandable}
	<div class="tree-node" style="padding-left: {depth * 16}px">
		<button class="toggle" onclick={toggle}>
			<span class="arrow" class:expanded>{'\u25B6'}</span>
		</button>
		{#if key}
			<span class="key">{key}</span><span class="colon">: </span>
		{/if}
		{#if !expanded}
			<span class="preview">{previewText()}</span>
		{:else}
			<span class="bracket">{isArray ? '[' : '{'}</span>
		{/if}
	</div>

	{#if expanded}
		{#each entries() as [k, v]}
			{#if v !== null && typeof v === 'object'}
				<svelte:self data={v} key={k} depth={depth + 1} {maxExpandDepth} />
			{:else}
				{@const fmt = formatValue(v)}
				<div class="tree-node" style="padding-left: {(depth + 1) * 16}px">
					<span class="spacer"></span>
					<span class="key">{k}</span><span class="colon">: </span>
					<span class={fmt.className}>{fmt.text}</span>
				</div>
			{/if}
		{/each}
		<div class="tree-node" style="padding-left: {depth * 16}px">
			<span class="spacer"></span>
			<span class="bracket">{isArray ? ']' : '}'}</span>
		</div>
	{/if}
{:else}
	{@const fmt = formatValue(data)}
	<div class="tree-node" style="padding-left: {depth * 16}px">
		<span class="spacer"></span>
		{#if key}
			<span class="key">{key}</span><span class="colon">: </span>
		{/if}
		<span class={fmt.className}>{fmt.text}</span>
	</div>
{/if}

<style>
	@reference "../../../app.css";

	.tree-node {
		display: flex;
		align-items: baseline;
		min-height: 1.375rem;
		font-family: var(--font-mono);
		font-size: 0.78125rem;
		line-height: 1.6;
		white-space: nowrap;
	}

	.toggle {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 1rem;
		height: 1rem;
		flex-shrink: 0;
		color: var(--color-gray-400);
		font-size: 0.5rem;
		transition: color 0.1s;
	}

	.toggle:hover {
		color: var(--color-gray-600);
	}

	:global(.dark) .toggle:hover {
		color: var(--color-gray-300);
	}

	.arrow {
		display: inline-block;
		transition: transform 0.15s;
	}

	.arrow.expanded {
		transform: rotate(90deg);
	}

	.spacer {
		width: 1rem;
		flex-shrink: 0;
	}

	.key {
		color: #2563eb;
	}

	:global(.dark) .key {
		color: #60a5fa;
	}

	.colon {
		color: var(--color-gray-500);
	}

	.preview {
		color: var(--color-gray-400);
		font-size: 0.6875rem;
	}

	.bracket {
		color: var(--color-gray-500);
	}

	.val-string {
		color: #16a34a;
	}

	:global(.dark) .val-string {
		color: #4ade80;
	}

	.val-number {
		color: #d97706;
	}

	:global(.dark) .val-number {
		color: #fbbf24;
	}

	.val-bool {
		color: #dc2626;
	}

	:global(.dark) .val-bool {
		color: #f87171;
	}

	.val-null {
		color: var(--color-gray-400);
		font-style: italic;
	}
</style>
