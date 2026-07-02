<script lang="ts">
	interface Props {
		page: number;
		totalPages: number;
		onpagechange: (page: number) => void;
	}
	let { page, totalPages, onpagechange }: Props = $props();
	import { t } from '$lib/i18n';

	// Build page numbers with ellipsis for large page counts
	const pages = $derived.by((): (number | 'ellipsis')[] => {
		if (totalPages <= 7) {
			return Array.from({ length: totalPages }, (_, i) => i + 1);
		}
		const items: (number | 'ellipsis')[] = [1];
		if (page > 3) items.push('ellipsis');
		const start = Math.max(2, page - 1);
		const end = Math.min(totalPages - 1, page + 1);
		for (let i = start; i <= end; i++) items.push(i);
		if (page < totalPages - 2) items.push('ellipsis');
		items.push(totalPages);
		return items;
	});
</script>

{#if totalPages > 1}
	<div class="pagination">
		<button
			class="pagination-btn"
			disabled={page <= 1}
			onclick={() => onpagechange(page - 1)}
			aria-label={$t('a11y.prevPage')}
		>
			<svg
				width="12"
				height="12"
				viewBox="0 0 12 12"
				fill="none"
				stroke="currentColor"
				stroke-width="1.75"
				stroke-linecap="round"
				stroke-linejoin="round"
			>
				<path d="M7.5 2.5L4 6L7.5 9.5" />
			</svg>
		</button>

		{#each pages as item, i (item === 'ellipsis' ? `e${i}` : item)}
			{#if item === 'ellipsis'}
				<span class="pagination-ellipsis">…</span>
			{:else}
				<button
					class="pagination-btn"
					class:active={item === page}
					onclick={() => onpagechange(item)}
					aria-label={$t('a11y.page', { page: item })}
					aria-current={item === page ? 'page' : undefined}
				>
					{item}
				</button>
			{/if}
		{/each}

		<button
			class="pagination-btn"
			disabled={page >= totalPages}
			onclick={() => onpagechange(page + 1)}
			aria-label={$t('a11y.nextPage')}
		>
			<svg
				width="12"
				height="12"
				viewBox="0 0 12 12"
				fill="none"
				stroke="currentColor"
				stroke-width="1.75"
				stroke-linecap="round"
				stroke-linejoin="round"
			>
				<path d="M4.5 2.5L8 6L4.5 9.5" />
			</svg>
		</button>
	</div>
{/if}

<style>
	.pagination {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.0625rem;
		padding-top: 0.5rem;
	}

	.pagination-btn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-width: 1.375rem;
		height: 1.375rem;
		padding: 0 0.1875rem;
		border: none;
		border-radius: 0.3125rem;
		background: transparent;
		color: #c4c4c4;
		font-size: 0.65625rem;
		font-weight: 500;
		cursor: pointer;
		transition:
			background 0.15s ease,
			color 0.15s ease;
		user-select: none;
	}

	.pagination-btn:hover:not(:disabled):not(.active) {
		background: rgba(0, 0, 0, 0.03);
		color: #9ca3af;
	}

	.pagination-btn.active {
		background: rgba(0, 0, 0, 0.04);
		color: #8b8b8b;
	}

	.pagination-btn:disabled {
		opacity: 0.25;
		cursor: not-allowed;
	}

	.pagination-ellipsis {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-width: 1.375rem;
		height: 1.375rem;
		font-size: 0.65625rem;
		color: #d1d5db;
		user-select: none;
		letter-spacing: 0.0625rem;
	}

	/* Dark mode */
	:global(.dark) .pagination-btn {
		color: #4b5563;
	}

	:global(.dark) .pagination-btn:hover:not(:disabled):not(.active) {
		background: rgba(255, 255, 255, 0.04);
		color: #6b7280;
	}

	:global(.dark) .pagination-btn.active {
		background: rgba(255, 255, 255, 0.06);
		color: #9ca3af;
	}

	:global(.dark) .pagination-ellipsis {
		color: #4b5563;
	}
</style>
