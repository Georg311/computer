<script lang="ts">
	import type { DiffHunk } from '$lib/utils/diff';
	import DiffHunkRows from './DiffHunkRows.svelte';

	interface Props {
		hunks: DiffHunk[];
		path: string;
		showNumbers?: boolean;
	}

	let { hunks, path, showNumbers = false }: Props = $props();
</script>

{#each hunks as hunk}
	{#if showNumbers}
		<div
			class="grid w-full grid-cols-[2.75rem_2.75rem_1.25rem_auto] border-b border-gray-100 bg-gray-50 text-gray-400 dark:border-white/4 dark:bg-white/3 dark:text-gray-600"
		>
			<span></span>
			<span></span>
			<span></span>
			<code class="whitespace-pre px-2 py-0.5">{hunk.header}</code>
		</div>
	{:else}
		<div
			class="w-full border-b border-gray-100 bg-gray-50 px-2 py-0.5 text-gray-400 dark:border-white/4 dark:bg-white/3 dark:text-gray-600"
		>
			{hunk.header}
		</div>
	{/if}
	<DiffHunkRows {hunk} {path} {showNumbers} />
{/each}
