<script lang="ts">
	import { tooltip } from '$lib/tooltip';
	import Icon from './Icon.svelte';
	import { t } from '$lib/i18n';

	interface Props {
		port: number;
	}

	let { port }: Props = $props();

	let path = $state('');
	let urlInput = $state(`localhost:${port}`);
	let iframeEl: HTMLIFrameElement | undefined = $state();
	let iframeKey = $state(0);
	let isLoading = $state(true);
	let loadError = $state(false);

	// ── Navigation history ──────────────────────────────────────────
	let history = $state<string[]>(['']);
	let historyIndex = $state(0);

	let canGoBack = $derived(historyIndex > 0);
	let canGoForward = $derived(historyIndex < history.length - 1);

	let proxyPathPrefix = $derived(`/api/proxy/${port}/`);
	let proxyUrl = $derived(`/api/proxy/${port}/${path}`);

	function makeDisplayUrl(p: string): string {
		return `localhost:${port}${p ? '/' + p : ''}`;
	}

	function syncUrlBar() {
		urlInput = makeDisplayUrl(path);
	}

	function pushHistory(newPath: string) {
		if (historyIndex < history.length - 1) {
			history = history.slice(0, historyIndex + 1);
		}
		history = [...history, newPath];
		historyIndex = history.length - 1;
	}

	function goBack() {
		if (!canGoBack) return;
		historyIndex -= 1;
		path = history[historyIndex];
		syncUrlBar();
		iframeKey += 1;
	}

	function goForward() {
		if (!canGoForward) return;
		historyIndex += 1;
		path = history[historyIndex];
		syncUrlBar();
		iframeKey += 1;
	}

	function refresh() {
		isLoading = true;
		loadError = false;
		iframeKey += 1;
	}

	function navigateUrl() {
		const stripped = urlInput.trim();
		const localhostPrefix = `localhost:${port}`;
		let newPath = '';

		if (stripped.startsWith(localhostPrefix)) {
			newPath = stripped.slice(localhostPrefix.length).replace(/^\//, '');
		} else if (stripped.startsWith('/') || !stripped.includes(':')) {
			newPath = stripped.replace(/^\//, '');
		}

		if (newPath !== path) {
			path = newPath;
			pushHistory(path);
		}
		syncUrlBar();
		iframeKey += 1;
	}

	function onIframeLoad() {
		isLoading = false;
		if (!iframeEl) return;
		try {
			const loc = iframeEl.contentWindow?.location;
			if (!loc) return;
			const iframePath = loc.pathname ?? '';
			const iframeSearch = loc.search ?? '';
			const iframeHash = loc.hash ?? '';

			if (iframePath.startsWith(proxyPathPrefix)) {
				const relativePath = iframePath.slice(proxyPathPrefix.length) + iframeSearch + iframeHash;
				if (relativePath !== path) {
					path = relativePath;
					pushHistory(path);
					syncUrlBar();
				}
			}
		} catch {
			// Cross-origin, can't access
		}
	}

	function openExternal() {
		window.open(`http://localhost:${port}/${path}`, '_blank');
	}

	function onKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter') {
			e.preventDefault();
			navigateUrl();
		}
	}
</script>

<div class="preview-container">
	<!-- Toolbar -->
	<div class="preview-toolbar">
		<!-- Back -->
		<button
			class="preview-btn {canGoBack ? '' : 'disabled'}"
			onclick={goBack}
			disabled={!canGoBack}
			use:tooltip={'Back'}
		>
			<Icon name="chevron-left" size={12} />
		</button>

		<!-- Forward -->
		<button
			class="preview-btn {canGoForward ? '' : 'disabled'}"
			onclick={goForward}
			disabled={!canGoForward}
			use:tooltip={'Forward'}
		>
			<Icon name="chevron-right" size={12} />
		</button>

		<!-- Refresh -->
		<button class="preview-btn" onclick={refresh} use:tooltip={'Refresh'}>
			<Icon name="refresh" size={12} />
		</button>

		<!-- URL bar -->
		<div class="url-bar">
			<input
				type="text"
				class="url-input"
				bind:value={urlInput}
				onkeydown={onKeydown}
				placeholder="localhost:{port}"
				spellcheck="false"
			/>
		</div>

		<!-- Open external -->
		<button class="preview-btn" onclick={openExternal} use:tooltip={'Open in new tab'}>
			<Icon name="external-link" size={12} />
		</button>
	</div>

	<!-- Loading bar -->
	{#if isLoading}
		<div class="loading-track">
			<div class="loading-bar"></div>
		</div>
	{/if}

	<!-- Content -->
	<div class="preview-content">
		{#if loadError}
			<div class="preview-error">
				<p class="error-title">{$t('port.cannotConnect')}</p>
				<p class="error-sub">localhost:{port} is not responding</p>
				<button class="error-retry" onclick={refresh}>Retry</button>
			</div>
		{:else}
			{#key iframeKey}
				<iframe
					bind:this={iframeEl}
					src={proxyUrl}
					title="Port {port} preview"
					sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-modals allow-downloads"
					class="preview-iframe"
					onload={onIframeLoad}
					onerror={() => {
						loadError = true;
						isLoading = false;
					}}
				></iframe>
			{/key}
		{/if}
	</div>
</div>

<style>
	@reference "../../app.css";

	.preview-container {
		display: flex;
		flex-direction: column;
		height: 100%;
		overflow: hidden;
	}

	.preview-toolbar {
		display: flex;
		align-items: center;
		gap: 0.25rem;
		height: 2rem;
		padding: 0 0.375rem;
		border-bottom: 1px solid var(--color-gray-200);
		flex-shrink: 0;
	}

	:global(.dark) .preview-toolbar {
		border-bottom-color: rgba(255, 255, 255, 0.06);
	}

	.preview-btn {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 1.375rem;
		height: 1.375rem;
		border-radius: 0.25rem;
		color: var(--color-gray-500);
		transition: all 0.1s;
		flex-shrink: 0;
	}

	.preview-btn:hover:not(.disabled) {
		background: var(--color-gray-100);
		color: var(--color-gray-700);
	}

	:global(.dark) .preview-btn {
		color: var(--color-gray-400);
	}

	:global(.dark) .preview-btn:hover:not(.disabled) {
		background: rgba(255, 255, 255, 0.06);
		color: var(--color-gray-300);
	}

	.preview-btn.disabled {
		color: var(--color-gray-300);
		cursor: default;
	}

	:global(.dark) .preview-btn.disabled {
		color: var(--color-gray-700);
	}

	.url-bar {
		flex: 1;
		min-width: 0;
	}

	.url-input {
		width: 100%;
		border: 1px solid var(--color-gray-200);
		border-radius: 624.9375rem;
		padding: 0.1875rem 0.75rem;
		font-size: 0.6875rem;
		font-family: var(--font-mono);
		background: white;
		color: var(--color-gray-600);
		outline: none;
		transition: border-color 0.1s;
	}

	.url-input:focus {
		border-color: oklch(0.65 0.15 250);
		box-shadow: 0 0 0 0.125rem oklch(0.65 0.15 250 / 0.15);
	}

	:global(.dark) .url-input {
		background: rgba(255, 255, 255, 0.04);
		border-color: rgba(255, 255, 255, 0.08);
		color: var(--color-gray-300);
	}

	:global(.dark) .url-input:focus {
		border-color: oklch(0.65 0.15 250);
		box-shadow: 0 0 0 0.125rem oklch(0.65 0.15 250 / 0.1);
	}

	.loading-track {
		height: 0.125rem;
		background: var(--color-gray-100);
		flex-shrink: 0;
		overflow: hidden;
	}

	:global(.dark) .loading-track {
		background: rgba(255, 255, 255, 0.04);
	}

	.loading-bar {
		height: 100%;
		background: oklch(0.65 0.15 250);
		border-radius: 624.9375rem;
		animation: loading-bar 1.5s ease-in-out infinite;
	}

	@keyframes loading-bar {
		0% {
			width: 0;
			margin-left: 0;
		}
		50% {
			width: 60%;
			margin-left: 20%;
		}
		100% {
			width: 0;
			margin-left: 100%;
		}
	}

	.preview-content {
		flex: 1;
		overflow: hidden;
		position: relative;
	}

	.preview-iframe {
		width: 100%;
		height: 100%;
		border: none;
		background: white;
	}

	.preview-error {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		height: 100%;
		gap: 0.375rem;
	}

	.error-title {
		font-size: 0.875rem;
		font-weight: 500;
		color: var(--color-gray-500);
	}

	.error-sub {
		font-size: 0.75rem;
		color: var(--color-gray-400);
		font-family: var(--font-mono);
	}

	.error-retry {
		margin-top: 0.5rem;
		padding: 0.25rem 0.875rem;
		border-radius: 0.375rem;
		font-size: 0.75rem;
		background: var(--color-gray-100);
		color: var(--color-gray-600);
		transition: all 0.1s;
	}

	.error-retry:hover {
		background: var(--color-gray-200);
	}

	:global(.dark) .error-retry {
		background: rgba(255, 255, 255, 0.06);
		color: var(--color-gray-300);
	}

	:global(.dark) .error-retry:hover {
		background: rgba(255, 255, 255, 0.1);
	}
</style>
