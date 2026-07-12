<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import panzoom, { type PanZoom } from 'panzoom';
	import { t } from '$lib/i18n';

	interface Props {
		src: string;
		alt?: string;
	}

	let { src, alt = '' }: Props = $props();

	let containerEl: HTMLDivElement | undefined = $state();
	let contentEl: HTMLDivElement | undefined = $state();
	let pzInstance: PanZoom | null = null;
	let zoomLevel = $state(1);

	function initPanzoom() {
		if (!contentEl) return;
		pzInstance?.dispose();

		pzInstance = panzoom(contentEl, {
			bounds: true,
			boundsPadding: 0.1,
			zoomSpeed: 0.065,
			smoothScroll: false,
			beforeMouseDown() {
				// Only drag-to-pan when zoomed in
				const transform = pzInstance?.getTransform();
				if (transform && Math.abs(transform.scale - 1) < 0.01) return true;
				return false;
			}
		});

		pzInstance.on('zoom', () => {
			zoomLevel = pzInstance?.getTransform()?.scale ?? 1;
		});
	}

	function zoomIn() {
		if (!pzInstance || !containerEl) return;
		const cx = containerEl.clientWidth / 2;
		const cy = containerEl.clientHeight / 2;
		pzInstance.zoomTo(cx, cy, 1.25);
		zoomLevel = pzInstance.getTransform().scale;
	}

	function zoomOut() {
		if (!pzInstance || !containerEl) return;
		const cx = containerEl.clientWidth / 2;
		const cy = containerEl.clientHeight / 2;
		pzInstance.zoomTo(cx, cy, 0.8);
		zoomLevel = pzInstance.getTransform().scale;
	}

	function resetView() {
		if (!pzInstance) return;
		pzInstance.moveTo(0, 0);
		pzInstance.zoomAbs(0, 0, 1);
		zoomLevel = 1;
	}

	onMount(() => {
		initPanzoom();
	});

	onDestroy(() => {
		pzInstance?.dispose();
		pzInstance = null;
	});
</script>

<div class="image-preview" bind:this={containerEl}>
	<div class="image-content" bind:this={contentEl}>
		<img {src} {alt} draggable="false" />
	</div>

	<div class="zoom-toolbar">
		<button class="zoom-btn" onclick={zoomOut} aria-label={$t('a11y.zoomOut')}>
			<svg
				xmlns="http://www.w3.org/2000/svg"
				viewBox="0 0 20 20"
				fill="currentColor"
				width="14"
				height="14"
			>
				<path
					fill-rule="evenodd"
					d="M4 10a.75.75 0 0 1 .75-.75h10.5a.75.75 0 0 1 0 1.5H4.75A.75.75 0 0 1 4 10Z"
					clip-rule="evenodd"
				/>
			</svg>
		</button>
		<button class="zoom-level" onclick={resetView} aria-label={$t('a11y.resetZoom')}>
			{Math.round(zoomLevel * 100)}%
		</button>
		<button class="zoom-btn" onclick={zoomIn} aria-label={$t('a11y.zoomIn')}>
			<svg
				xmlns="http://www.w3.org/2000/svg"
				viewBox="0 0 20 20"
				fill="currentColor"
				width="14"
				height="14"
			>
				<path
					d="M10.75 4.75a.75.75 0 0 0-1.5 0v4.5h-4.5a.75.75 0 0 0 0 1.5h4.5v4.5a.75.75 0 0 0 1.5 0v-4.5h4.5a.75.75 0 0 0 0-1.5h-4.5v-4.5Z"
				/>
			</svg>
		</button>
	</div>
</div>

<style>
	@reference "../../../app.css";

	.image-preview {
		position: relative;
		width: 100%;
		height: 100%;
		overflow: hidden;
		background: repeating-conic-gradient(var(--app-hover) 0% 25%, transparent 0% 50%) 50% /
			1rem 1rem;
	}

	.image-content {
		width: 100%;
		height: 100%;
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.image-content img {
		max-width: 100%;
		max-height: 100%;
		object-fit: contain;
		padding: 0.75rem;
		user-select: none;
	}

	.zoom-toolbar {
		position: absolute;
		bottom: 0.75rem;
		left: 50%;
		transform: translateX(-50%);
		display: flex;
		align-items: center;
		gap: 0.125rem;
		padding: 0.125rem;
		border-radius: 0.5rem;
		background: color-mix(in oklab, var(--app-bg) 90%, transparent);
		backdrop-filter: blur(0.5rem);
		border: 1px solid var(--app-border);
		box-shadow: 0 0.125rem 0.5rem color-mix(in oklab, var(--app-fg) 10%, transparent);
	}

	.zoom-btn {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 1.75rem;
		height: 1.75rem;
		border-radius: 0.375rem;
		color: var(--app-fg-muted);
		transition: all 0.1s;
	}

	.zoom-btn:hover {
		background: var(--app-hover);
		color: var(--app-fg);
	}

	.zoom-level {
		min-width: 3rem;
		padding: 0.25rem 0.375rem;
		font-size: 0.6875rem;
		font-weight: 500;
		text-align: center;
		color: var(--app-fg-muted);
		border-radius: 0.375rem;
		font-variant-numeric: tabular-nums;
		transition: all 0.1s;
	}

	.zoom-level:hover {
		background: var(--app-hover);
		color: var(--app-fg);
	}
</style>
