<script lang="ts">
	import { tooltip } from '$lib/tooltip';
	import Icon from '../Icon.svelte';
	import panzoom, { type PanZoom } from 'panzoom';
	import { onMount, onDestroy } from 'svelte';
	import DOMPurify from 'dompurify';

	interface Props {
		content: string;
	}

	let { content }: Props = $props();

	let mode = $state<'visual' | 'source'>('visual');
	let containerEl: HTMLDivElement | undefined = $state();
	let contentEl: HTMLDivElement | undefined = $state();
	let pzInstance: PanZoom | null = null;
	let zoomLevel = $state(1);

	let sanitizedSvg = $derived(
		DOMPurify.sanitize(content, { USE_PROFILES: { svg: true, svgFilters: true } })
	);

	function initPanzoom() {
		if (!contentEl) return;
		pzInstance?.dispose();

		pzInstance = panzoom(contentEl, {
			bounds: true,
			boundsPadding: 0.1,
			zoomSpeed: 0.065,
			smoothScroll: false,
			beforeMouseDown() {
				const t = pzInstance?.getTransform();
				if (t && Math.abs(t.scale - 1) < 0.01) return true;
				return false;
			}
		});

		pzInstance.on('zoom', () => {
			zoomLevel = pzInstance?.getTransform()?.scale ?? 1;
		});
	}

	function resetView() {
		if (!pzInstance) return;
		pzInstance.moveTo(0, 0);
		pzInstance.zoomAbs(0, 0, 1);
		zoomLevel = 1;
	}

	$effect(() => {
		if (mode === 'visual' && contentEl) {
			// Wait for DOM update
			requestAnimationFrame(() => initPanzoom());
		} else {
			pzInstance?.dispose();
			pzInstance = null;
		}
	});

	onDestroy(() => {
		pzInstance?.dispose();
		pzInstance = null;
	});
</script>

<div class="svg-preview">
	<div class="toolbar">
		<div class="toolbar-left">
			<span class="file-label">SVG</span>
		</div>
		<div class="toolbar-right">
			<button
				class="toolbar-btn"
				class:active={mode === 'visual'}
				onclick={() => {
					mode = 'visual';
				}}
				use:tooltip={'Visual'}><Icon name="eye" size={14} /></button
			>
			<button
				class="toolbar-btn"
				class:active={mode === 'source'}
				onclick={() => {
					mode = 'source';
				}}
				use:tooltip={'Source'}><Icon name="code" size={14} /></button
			>
			{#if mode === 'visual'}
				<button class="toolbar-btn" onclick={resetView} use:tooltip={'Reset zoom'}>
					<span class="zoom-text">{Math.round(zoomLevel * 100)}%</span>
				</button>
			{/if}
		</div>
	</div>

	<div class="content-area">
		{#if mode === 'visual'}
			<div class="visual-container" bind:this={containerEl}>
				<div class="visual-content" bind:this={contentEl}>
					{@html sanitizedSvg}
				</div>
			</div>
		{:else}
			<pre class="source-view">{content}</pre>
		{/if}
	</div>
</div>

<style>
	@reference "../../../app.css";

	.svg-preview {
		display: flex;
		flex-direction: column;
		height: 100%;
		overflow: hidden;
	}

	.toolbar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		height: 2.25rem;
		padding: 0 0.75rem;
		border-bottom: 1px solid var(--color-gray-200);
		flex-shrink: 0;
	}

	:global(.dark) .toolbar {
		border-bottom-color: rgba(255, 255, 255, 0.06);
	}

	.toolbar-left {
		display: flex;
		align-items: center;
	}

	.toolbar-right {
		display: flex;
		align-items: center;
		gap: 0.125rem;
	}

	.file-label {
		font-size: 0.6875rem;
		font-weight: 500;
		color: var(--color-gray-500);
	}

	.toolbar-btn {
		display: flex;
		align-items: center;
		justify-content: center;
		min-width: 1.5rem;
		height: 1.5rem;
		padding: 0 0.25rem;
		border-radius: 0.375rem;
		color: var(--color-gray-400);
		transition: all 0.1s;
	}

	.toolbar-btn:hover {
		color: var(--color-gray-600);
	}

	:global(.dark) .toolbar-btn:hover {
		color: var(--color-gray-300);
	}

	.toolbar-btn.active {
		color: var(--color-gray-900);
	}

	:global(.dark) .toolbar-btn.active {
		color: white;
	}

	.zoom-text {
		font-size: 0.625rem;
		font-weight: 500;
		font-variant-numeric: tabular-nums;
	}

	.content-area {
		flex: 1;
		overflow: hidden;
	}

	.visual-container {
		width: 100%;
		height: 100%;
		overflow: hidden;
		background: repeating-conic-gradient(var(--color-gray-100) 0% 25%, transparent 0% 50%) 50% /
			1rem 1rem;
	}

	:global(.dark) .visual-container {
		background: repeating-conic-gradient(rgba(255, 255, 255, 0.04) 0% 25%, transparent 0% 50%) 50% /
			1rem 1rem;
	}

	.visual-content {
		width: 100%;
		height: 100%;
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 1.5rem;
	}

	.visual-content :global(svg) {
		max-width: 100%;
		max-height: 100%;
	}

	.source-view {
		width: 100%;
		height: 100%;
		overflow: auto;
		margin: 0;
		padding: 0.75rem 1rem;
		font-family: var(--font-mono);
		font-size: 0.78125rem;
		line-height: 1.6;
		color: var(--color-gray-800);
		white-space: pre-wrap;
		word-break: break-all;
	}

	:global(.dark) .source-view {
		color: var(--color-gray-200);
	}
</style>
