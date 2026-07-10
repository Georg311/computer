<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import { tooltip } from '$lib/tooltip';
	import {
		browserBlankUrl,
		browserFrameUrl,
		getBrowserSession,
		updateBrowserSession
	} from '$lib/apis/browser';
	import { openBrowserTab } from '$lib/stores';
	import Icon from './Icon.svelte';
	import { t } from '$lib/i18n';

	interface Props {
		sessionId: string;
		groupId: string;
		initialUrl?: string;
	}

	let { sessionId, groupId, initialUrl }: Props = $props();
	let iframeEl: HTMLIFrameElement | undefined = $state();
	let frameSrc = $state(browserBlankUrl(sessionId));
	let urlInput = $state(initialUrl ?? '');
	let title = $state('');
	let loading = $state(false);
	let error = $state('');

	function publicUrl(value: string) {
		const proxyUrl = new URL(value, location.origin);
		if (proxyUrl.pathname === `/api/browser/frame/${sessionId}`)
			return proxyUrl.searchParams.get('url') || value;
		const marker = `/api/browser/frame/${sessionId}/`;
		const index = proxyUrl.pathname.indexOf(marker);
		if (index === -1) return value;
		const [scheme, encodedHost, ...path] = proxyUrl.pathname
			.slice(index + marker.length)
			.split('/');
		const host = decodeURIComponent(encodedHost || '');
		return scheme && host
			? `${scheme}://${host}/${path.join('/')}${proxyUrl.search}${proxyUrl.hash}`
			: value;
	}

	function navigate(url = urlInput) {
		const value = url.trim();
		if (!value) return;
		try {
			urlInput = new URL(
				/^https?:\/\//i.test(publicUrl(value)) ? publicUrl(value) : `https://${publicUrl(value)}`
			).href;
			frameSrc = browserFrameUrl(sessionId, urlInput);
			loading = true;
			error = '';
			void updateBrowserSession(sessionId, urlInput, title).catch(() => {});
		} catch {
			error = $t('browser.invalidUrl');
		}
	}

	function refresh() {
		loading = true;
		iframeEl?.contentWindow?.location.reload();
	}

	function frameLoaded() {
		loading = false;
		try {
			const current = new URL(iframeEl?.contentWindow?.location.href || '');
			const framePrefix = `/api/browser/frame/${sessionId}`;
			const blankPath = `/api/browser/sessions/${sessionId}/blank`;
			if (current.origin !== location.origin || current.pathname.startsWith(framePrefix) || current.pathname === blankPath)
				return;

			const upstream = new URL(`${current.pathname}${current.search}${current.hash}`, urlInput).href;
			urlInput = upstream;
			loading = true;
			void updateBrowserSession(sessionId, upstream, title).catch(() => {});
			iframeEl?.contentWindow?.location.replace(browserFrameUrl(sessionId, upstream));
		} catch {
			// Cross-origin frames cannot be inspected; the proxy frame is same-origin.
		}
	}

	function receiveMessage(event: MessageEvent) {
		if (event.origin !== location.origin || event.source !== iframeEl?.contentWindow) return;
		const data = event.data;
		if (data?.type === 'cptr-browser-state') {
			urlInput = publicUrl(data.url || urlInput);
			title = data.title || '';
			loading = false;
			void updateBrowserSession(sessionId, urlInput, title).catch(() => {});
		}
		if (data?.type === 'cptr-browser-popup' && data.url) openBrowserTab(groupId, data.url);
	}

	onMount(() => {
		window.addEventListener('message', receiveMessage);
		void getBrowserSession(sessionId)
			.then((session) => {
				const url = publicUrl(session.url || initialUrl || '');
				title = session.title;
				if (url) navigate(url);
			})
			.catch(() => {});
	});
	onDestroy(() => window.removeEventListener('message', receiveMessage));
</script>

<div class="preview-container">
	<div class="preview-toolbar">
		<button
			class="preview-btn"
			onclick={() => iframeEl?.contentWindow?.history.back()}
			use:tooltip={$t('settings.back')}
		>
			<Icon name="chevron-left" size={12} />
		</button>
		<button
			class="preview-btn"
			onclick={() => iframeEl?.contentWindow?.history.forward()}
			use:tooltip={$t('common.forward')}
		>
			<Icon name="chevron-right" size={12} />
		</button>
		<button class="preview-btn" onclick={refresh} use:tooltip={$t('files.refresh')}>
			<Icon name="refresh" size={12} />
		</button>
		<div class="url-bar">
			<input
				class="url-input"
				bind:value={urlInput}
				onkeydown={(event) => event.key === 'Enter' && navigate()}
				placeholder="https://example.com"
				spellcheck="false"
			/>
		</div>
		{#if title}<span class="browser-title" {title}>{title}</span>{/if}
	</div>
	{#if loading}<div class="loading-track"><div class="loading-bar"></div></div>{/if}
	<div class="preview-content">
		{#if error}
			<div class="preview-error">
				<p class="error-title">{error}</p>
				<button class="error-retry" onclick={() => navigate()}>{$t('files.retry')}</button>
			</div>
		{:else}
			<iframe
				bind:this={iframeEl}
				src={frameSrc}
				title={title || $t('bar.newBrowser')}
				class="preview-iframe"
				onload={frameLoaded}
				onerror={() => {
					error = $t('port.cannotConnect');
					loading = false;
				}}
			></iframe>
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
	.preview-btn {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 1.375rem;
		height: 1.375rem;
		border-radius: 0.25rem;
		color: var(--color-gray-500);
		flex-shrink: 0;
	}
	.preview-btn:hover {
		background: var(--color-gray-100);
		color: var(--color-gray-700);
	}
	.url-bar {
		flex: 1;
		min-width: 0;
	}
	.url-input {
		width: 100%;
		border: 1px solid var(--color-gray-200);
		border-radius: 999px;
		padding: 0.1875rem 0.75rem;
		font-size: 0.6875rem;
		font-family: var(--font-mono);
		background: white;
		color: var(--color-gray-600);
		outline: none;
	}
	.browser-title {
		max-width: 10rem;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-size: 0.6875rem;
		color: var(--color-gray-500);
	}
	.preview-content {
		flex: 1;
		min-height: 0;
		position: relative;
	}
	.preview-iframe {
		width: 100%;
		height: 100%;
		border: 0;
		display: block;
		background: white;
	}
	.loading-track {
		height: 2px;
		overflow: hidden;
		background: var(--color-gray-100);
	}
	.loading-bar {
		height: 100%;
		width: 35%;
		background: var(--color-brand-500);
		animation: browser-loading 1s ease-in-out infinite;
	}
	.preview-error {
		height: 100%;
		display: grid;
		place-content: center;
		gap: 0.5rem;
		text-align: center;
	}
	.error-retry {
		color: var(--color-brand-600);
	}
	@keyframes browser-loading {
		from {
			transform: translateX(-120%);
		}
		to {
			transform: translateX(320%);
		}
	}
	:global(.dark) .preview-toolbar {
		border-color: rgba(255, 255, 255, 0.06);
	}
	:global(.dark) .url-input {
		background: rgba(255, 255, 255, 0.04);
		border-color: rgba(255, 255, 255, 0.08);
		color: var(--color-gray-300);
	}
	:global(.dark) .preview-btn:hover {
		background: rgba(255, 255, 255, 0.06);
		color: var(--color-gray-300);
	}
</style>
