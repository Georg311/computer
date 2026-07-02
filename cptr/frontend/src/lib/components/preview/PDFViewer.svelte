<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import panzoom, { type PanZoom } from 'panzoom';
	import { fetchHandler } from '$lib/apis';
	import Spinner from '$lib/components/common/Spinner.svelte';

	interface Props {
		src: string;
	}

	let { src }: Props = $props();

	let outerEl: HTMLDivElement | undefined = $state();
	let sceneEl: HTMLDivElement | undefined = $state();
	let loading = $state(true);
	let error = $state('');
	let pzInstance: PanZoom | null = null;
	let zoomLevel = $state(1);
	let pdfDoc: any = null;
	let lastRenderedZoom = 1;
	let rerenderTimer: ReturnType<typeof setTimeout> | null = null;
	let textLayers: any[] = [];

	async function loadPdf() {
		if (!src) return;
		loading = true;
		error = '';

		try {
			const pdfjs = await import('pdfjs-dist');

			// Set up worker
			const workerUrl = await import('pdfjs-dist/build/pdf.worker.mjs?url');
			pdfjs.GlobalWorkerOptions.workerSrc = workerUrl.default;

			const res = await fetchHandler(src);
			if (!res.ok) throw new Error(`HTTP ${res.status}`);
			const data = await res.arrayBuffer();

			pdfDoc = await pdfjs.getDocument({ data }).promise;
			await renderAllPages();
		} catch (e: any) {
			console.error('PDF render error:', e);
			error = 'Failed to load PDF.';
		} finally {
			loading = false;
		}
	}

	async function renderAllPages() {
		if (!pdfDoc || !sceneEl) return;
		sceneEl.innerHTML = '';
		cancelTextLayers();

		const pdfjs = await import('pdfjs-dist');
		const dpr = window.devicePixelRatio || 1;

		for (let i = 1; i <= pdfDoc.numPages; i++) {
			const page = await pdfDoc.getPage(i);
			const viewport = page.getViewport({ scale: 1 });

			const containerWidth = outerEl?.clientWidth || 800;
			const cssScale = containerWidth / viewport.width;
			const renderScale = cssScale * dpr;
			const scaledViewport = page.getViewport({ scale: renderScale });
			const cssViewport = page.getViewport({ scale: cssScale });

			// Page wrapper
			const wrapper = document.createElement('div');
			wrapper.className = 'pdf-page';
			wrapper.style.position = 'relative';
			wrapper.style.width = `${Math.round(cssScale * viewport.width)}px`;
			wrapper.style.height = `${Math.round(cssScale * viewport.height)}px`;
			wrapper.style.setProperty('--scale-factor', String(cssViewport.scale));
			if (i > 1) wrapper.style.marginTop = '0.25rem';

			// Canvas
			const canvas = document.createElement('canvas');
			canvas.width = scaledViewport.width;
			canvas.height = scaledViewport.height;
			canvas.style.width = `${Math.round(cssScale * viewport.width)}px`;
			canvas.style.height = `${Math.round(cssScale * viewport.height)}px`;
			canvas.style.display = 'block';
			wrapper.appendChild(canvas);

			const ctx = canvas.getContext('2d');
			await page.render({ canvasContext: ctx, viewport: scaledViewport }).promise;

			// Text layer for selection/search
			const textDiv = document.createElement('div');
			textDiv.className = 'textLayer';
			wrapper.appendChild(textDiv);

			const textContent = await page.getTextContent();
			const textLayer = new pdfjs.TextLayer({
				textContentSource: textContent,
				container: textDiv,
				viewport: cssViewport
			});
			await textLayer.render();
			textLayers.push(textLayer);

			sceneEl.appendChild(wrapper);
		}

		lastRenderedZoom = 1;
		initPanzoom();
	}

	async function rerenderPages(forZoom: number) {
		if (!pdfDoc || !sceneEl) return;
		const pdfjs = await import('pdfjs-dist');
		const dpr = window.devicePixelRatio || 1;
		const containerWidth = outerEl?.clientWidth || 800;
		const wrappers = sceneEl.querySelectorAll('.pdf-page');

		cancelTextLayers();

		for (let i = 0; i < wrappers.length; i++) {
			const page = await pdfDoc.getPage(i + 1);
			const viewport = page.getViewport({ scale: 1 });
			const cssScale = containerWidth / viewport.width;
			const renderScale = cssScale * forZoom * dpr;
			const scaledViewport = page.getViewport({ scale: renderScale });
			const cssViewport = page.getViewport({ scale: cssScale });

			const wrapper = wrappers[i] as HTMLElement;
			wrapper.style.setProperty('--scale-factor', String(cssViewport.scale));

			const canvas = wrapper.querySelector('canvas')!;
			canvas.width = scaledViewport.width;
			canvas.height = scaledViewport.height;

			const ctx = canvas.getContext('2d');
			if (ctx) {
				await page.render({ canvasContext: ctx, viewport: scaledViewport }).promise;
			}

			const textDiv = wrapper.querySelector('.textLayer') as HTMLElement;
			if (textDiv) {
				textDiv.innerHTML = '';
				const textContent = await page.getTextContent();
				const tl = new pdfjs.TextLayer({
					textContentSource: textContent,
					container: textDiv,
					viewport: cssViewport
				});
				await tl.render();
				textLayers.push(tl);
			}
		}
		lastRenderedZoom = forZoom;
	}

	function cancelTextLayers() {
		for (const tl of textLayers) {
			try {
				tl.cancel();
			} catch {}
		}
		textLayers = [];
	}

	function initPanzoom() {
		pzInstance?.dispose();
		if (!sceneEl) return;

		pzInstance = panzoom(sceneEl, {
			bounds: true,
			boundsPadding: 0.1,
			zoomSpeed: 0.065,
			smoothScroll: false,
			beforeWheel(e) {
				if (!e.ctrlKey && !e.metaKey) return true;
				return false;
			},
			beforeMouseDown() {
				const t = pzInstance?.getTransform();
				if (t && Math.abs(t.scale - 1) < 0.01) return true;
				return false;
			}
		});

		pzInstance.on('zoom', () => {
			zoomLevel = pzInstance?.getTransform()?.scale ?? 1;
			if (rerenderTimer) clearTimeout(rerenderTimer);
			rerenderTimer = setTimeout(() => {
				if (Math.abs(zoomLevel - lastRenderedZoom) > 0.05) {
					rerenderPages(zoomLevel);
				}
			}, 300);
		});
	}

	function zoomIn() {
		if (!pzInstance || !outerEl) return;
		pzInstance.zoomTo(outerEl.clientWidth / 2, outerEl.clientHeight / 2, 1.25);
		zoomLevel = pzInstance.getTransform().scale;
	}

	function zoomOut() {
		if (!pzInstance || !outerEl) return;
		pzInstance.zoomTo(outerEl.clientWidth / 2, outerEl.clientHeight / 2, 0.8);
		zoomLevel = pzInstance.getTransform().scale;
	}

	function resetView() {
		if (!pzInstance) return;
		pzInstance.moveTo(0, 0);
		pzInstance.zoomAbs(0, 0, 1);
		zoomLevel = 1;
		rerenderPages(1);
	}

	onMount(() => {
		loadPdf();
	});

	onDestroy(() => {
		if (rerenderTimer) clearTimeout(rerenderTimer);
		pzInstance?.dispose();
		cancelTextLayers();
		if (pdfDoc) {
			pdfDoc.destroy();
			pdfDoc = null;
		}
	});
</script>

<div class="pdf-viewer">
	{#if loading}
		<div class="state"><Spinner size={20} /></div>
	{:else if error}
		<div class="state error-msg">{error}</div>
	{/if}

	<div class="pdf-scroll" bind:this={outerEl}>
		<div bind:this={sceneEl} class="pdf-scene"></div>
	</div>

	{#if !loading && !error && pdfDoc}
		<div class="zoom-toolbar">
			<button class="zoom-btn" onclick={zoomOut} aria-label="Zoom out">
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
			<button class="zoom-level" onclick={resetView} aria-label="Reset zoom">
				{Math.round(zoomLevel * 100)}%
			</button>
			<button class="zoom-btn" onclick={zoomIn} aria-label="Zoom in">
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
	{/if}
</div>

<style>
	@reference "../../../app.css";

	.pdf-viewer {
		position: relative;
		width: 100%;
		height: 100%;
	}

	.pdf-scroll {
		width: 100%;
		height: 100%;
		overflow-y: auto;
	}

	.pdf-scene {
		width: 100%;
	}

	.state {
		position: absolute;
		inset: 0;
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 1;
	}

	.error-msg {
		font-size: 0.8125rem;
		color: #ef4444;
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
		background: rgba(255, 255, 255, 0.9);
		backdrop-filter: blur(0.5rem);
		border: 1px solid rgba(0, 0, 0, 0.08);
		box-shadow: 0 0.125rem 0.5rem rgba(0, 0, 0, 0.1);
		z-index: 10;
	}

	:global(.dark) .zoom-toolbar {
		background: rgba(30, 30, 30, 0.9);
		border-color: rgba(255, 255, 255, 0.1);
		box-shadow: 0 0.125rem 0.5rem rgba(0, 0, 0, 0.3);
	}

	.zoom-btn {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 1.75rem;
		height: 1.75rem;
		border-radius: 0.375rem;
		color: var(--color-gray-500);
		transition: all 0.1s;
	}

	.zoom-btn:hover {
		background: rgba(0, 0, 0, 0.06);
		color: var(--color-gray-700);
	}

	:global(.dark) .zoom-btn:hover {
		background: rgba(255, 255, 255, 0.1);
		color: var(--color-gray-300);
	}

	.zoom-level {
		min-width: 3rem;
		padding: 0.25rem 0.375rem;
		font-size: 0.6875rem;
		font-weight: 500;
		text-align: center;
		color: var(--color-gray-500);
		border-radius: 0.375rem;
		font-variant-numeric: tabular-nums;
		transition: all 0.1s;
	}

	.zoom-level:hover {
		background: rgba(0, 0, 0, 0.06);
		color: var(--color-gray-700);
	}

	:global(.dark) .zoom-level:hover {
		background: rgba(255, 255, 255, 0.1);
		color: var(--color-gray-300);
	}

	/* ── pdfjs TextLayer styles ─────────────────────────────────── */

	:global(.textLayer) {
		position: absolute;
		inset: 0;
		overflow: clip;
		opacity: 1;
		line-height: 1;
		text-size-adjust: none;
		forced-color-adjust: none;
		transform-origin: 0 0;
		caret-color: CanvasText;
		z-index: 0;
	}

	:global(.textLayer) {
		--user-unit: 1;
		--total-scale-factor: calc(var(--scale-factor) * var(--user-unit));
		--min-font-size: 1;
		--text-scale-factor: calc(var(--total-scale-factor) * var(--min-font-size));
		--min-font-size-inv: calc(1 / var(--min-font-size));
	}

	:global(.textLayer :is(span, br)) {
		color: transparent;
		position: absolute;
		white-space: pre;
		cursor: text;
		transform-origin: 0% 0%;
	}

	:global(.textLayer > :not(.markedContent)),
	:global(.textLayer .markedContent span:not(.markedContent)) {
		z-index: 1;
		--font-height: 0;
		font-size: calc(var(--text-scale-factor) * var(--font-height));
		--scale-x: 1;
		--rotate: 0deg;
		transform: rotate(var(--rotate)) scaleX(var(--scale-x)) scale(var(--min-font-size-inv));
	}

	:global(.textLayer .markedContent) {
		display: contents;
	}

	:global(.textLayer ::selection) {
		background: rgba(0, 100, 255, 0.25);
	}

	:global(.textLayer br::selection) {
		background: transparent;
	}
</style>
