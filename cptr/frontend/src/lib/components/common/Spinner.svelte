<script lang="ts">
	import { t } from '$lib/i18n';

	interface Props {
		/** Size in px or Tailwind class like '3.5' or '5'. Defaults to 1rem. */
		size?: number | string;
		/** Border width in px. Scales automatically if not set. */
		borderWidth?: number;
		/** Extra CSS classes. */
		class?: string;
	}
	let { size = 16, borderWidth, class: className = '' }: Props = $props();

	const px = typeof size === 'number' ? size : parseFloat(size) * 4;
	const bw = borderWidth ?? (px <= 12 ? 1.5 : 2);
</script>

<div
	class="spinner {className}"
	style="width:{px}px;height:{px}px;border-width:{bw}px"
	role="status"
	aria-label={$t('common.loading')}
></div>

<style>
	.spinner {
		display: inline-block;
		border-style: solid;
		border-color: var(--color-gray-300);
		border-top-color: var(--color-gray-600);
		border-radius: 624.9375rem;
		animation: spin 0.75s linear infinite;
		flex-shrink: 0;
	}

	:global(.dark) .spinner {
		border-color: var(--color-gray-700);
		border-top-color: var(--color-gray-400);
	}

	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}
</style>
