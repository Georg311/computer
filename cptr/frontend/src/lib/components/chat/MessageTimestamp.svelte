<script lang="ts">
	import { tooltip } from '$lib/tooltip';

	interface Props {
		createdAt?: number | null;
		side?: 'left' | 'right';
	}

	let { createdAt = null, side = 'right' }: Props = $props();

	function toDate(ts: number | null | undefined): Date | null {
		if (!ts) return null;
		const date = new Date(ts < 1_000_000_000_000 ? ts * 1000 : ts);
		return Number.isNaN(date.getTime()) ? null : date;
	}

	const date = $derived(toDate(createdAt));
	const label = $derived(
		date?.toLocaleString(undefined, {
			month: 'short',
			day: 'numeric',
			hour: 'numeric',
			minute: '2-digit'
		}) ?? ''
	);
	const fullLabel = $derived(
		date?.toLocaleString(undefined, {
			weekday: 'long',
			year: 'numeric',
			month: 'long',
			day: 'numeric',
			hour: 'numeric',
			minute: '2-digit'
		}) ?? ''
	);
</script>

{#if date && label}
	<time
		datetime={date.toISOString()}
		class="{side === 'left'
			? 'mr-1'
			: 'ml-1'} text-[0.6875rem] tabular-nums text-gray-400 dark:text-gray-600 select-none opacity-0 pointer-events-none transition-opacity duration-100 group-hover/timestamp-toolbar:opacity-100 group-hover/timestamp-toolbar:pointer-events-auto group-focus-within/timestamp-toolbar:opacity-100 group-focus-within/timestamp-toolbar:pointer-events-auto"
		use:tooltip={fullLabel}
	>
		{label}
	</time>
{/if}
