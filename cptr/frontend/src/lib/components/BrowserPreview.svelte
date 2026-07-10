<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import { tooltip } from '$lib/tooltip';
	import {
		browserBlankUrl,
		browserFrameUrl,
		getBrowserSession,
		setBrowserMode,
		updateBrowserSession
	} from '$lib/apis/browser';
	import { openBrowserTab, updateTabLabel } from '$lib/stores';
	import Icon from './Icon.svelte';
	import ChromeBrowser from './ChromeBrowser.svelte';
	import Spinner from './common/Spinner.svelte';
	import { t } from '$lib/i18n';

	interface Props {
		sessionId: string;
		groupId: string;
		tabId: string;
		initialUrl?: string;
		active?: boolean;
	}

	let { sessionId, groupId, tabId, initialUrl, active = true }: Props = $props();
	let iframeEl: HTMLIFrameElement | undefined = $state();
	let chromeEl: ChromeBrowser | undefined = $state();
	let frameSrc = $state(browserBlankUrl(sessionId));
	let urlInput = $state(initialUrl ?? '');
	let title = $state('');
	let loading = $state(false);
	let error = $state('');
	let modeError = $state('');
	let mode = $state<'proxy' | 'chrome'>('proxy');
	let chromeStatus = $state('');
	let canGoBack = $state(false);
	let canGoForward = $state(false);

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
			if (mode === 'chrome') chromeEl?.navigate(urlInput);
			else frameSrc = browserFrameUrl(sessionId, urlInput);
			loading = true;
			error = '';
			void updateBrowserSession(sessionId, urlInput, title).catch(() => {});
		} catch {
			error = $t('browser.invalidUrl');
		}
	}

	function newTabUrl(value: string) {
		try {
			const canonical = publicUrl(value.trim());
			return canonical
				? new URL(/^https?:\/\//i.test(canonical) ? canonical : `https://${canonical}`).href
				: '';
		} catch {
			return '';
		}
	}

	function refresh() {
		loading = true;
		if (mode === 'chrome') chromeEl?.reload();
		else iframeEl?.contentWindow?.location.reload();
	}

	function frameLoaded() {
		loading = false;
		try {
			const current = new URL(iframeEl?.contentWindow?.location.href || '');
			const framePrefix = `/api/browser/frame/${sessionId}`;
			const blankPath = `/api/browser/sessions/${sessionId}/blank`;
			if (
				current.origin !== location.origin ||
				current.pathname.startsWith(framePrefix) ||
				current.pathname === blankPath
			)
				return;

			const upstream = new URL(`${current.pathname}${current.search}${current.hash}`, urlInput)
				.href;
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
			updateTabLabel(tabId, title);
			loading = false;
			void updateBrowserSession(sessionId, urlInput, title).catch(() => {});
		}
		if (data?.type === 'cptr-browser-popup' && data.url) openBrowserTab(groupId, data.url);
	}

	onMount(() => {
		window.addEventListener('message', receiveMessage);
		void getBrowserSession(sessionId)
			.then(async (session) => {
				const url = publicUrl(session.url || initialUrl || '');
				urlInput = url;
				title = session.title;
				updateTabLabel(tabId, title);
				mode = session.mode || 'proxy';
				if (mode === 'chrome') {
					chromeStatus = 'connecting';
					loading = true;
					const supported =
						'VideoDecoder' in window &&
						(await VideoDecoder.isConfigSupported({ codec: 'avc1.42E028' })).supported;
					if (!supported) {
						mode = 'proxy';
						modeError = $t('browser.decoderUnavailable');
						void setBrowserMode(sessionId, 'proxy', url).catch(() => {});
					}
				}
				if (url && mode === 'proxy') navigate(url);
			})
			.catch(() => {});
	});
	onDestroy(() => window.removeEventListener('message', receiveMessage));
</script>

<div class="flex h-full min-w-0 flex-col overflow-hidden">
	<div
		class="flex min-w-0 shrink-0 items-center gap-1 border-b border-gray-200 px-1.5 py-[3px] sm:px-2 dark:border-white/6"
	>
		<button
			class="flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-700 disabled:pointer-events-none disabled:opacity-35 dark:hover:bg-white/6 dark:hover:text-gray-300"
			disabled={mode === 'chrome' && !canGoBack}
			onclick={() =>
				mode === 'chrome' ? chromeEl?.back() : iframeEl?.contentWindow?.history.back()}
			use:tooltip={$t('settings.back')}
		>
			<Icon name="chevron-left" size={12} />
		</button>
		<button
			class="flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-700 disabled:pointer-events-none disabled:opacity-35 dark:hover:bg-white/6 dark:hover:text-gray-300"
			disabled={mode === 'chrome' && !canGoForward}
			onclick={() =>
				mode === 'chrome' ? chromeEl?.forward() : iframeEl?.contentWindow?.history.forward()}
			use:tooltip={$t('common.forward')}
		>
			<Icon name="chevron-right" size={12} />
		</button>
		<button
			class="flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-700 dark:hover:bg-white/6 dark:hover:text-gray-300"
			onclick={refresh}
			use:tooltip={$t('files.refresh')}
		>
			<Icon name="refresh" size={12} />
		</button>
		<div class="relative min-w-0 flex-1">
			<input
				class="h-7 w-full min-w-0 rounded-full bg-transparent py-1 pr-8 pl-3 text-left text-xs font-medium text-gray-700 outline-none transition-colors hover:bg-gray-100/60 focus:bg-gray-100 sm:px-8 sm:text-center dark:text-gray-300 dark:hover:bg-white/5 dark:focus:bg-white/8"
				bind:value={urlInput}
				onkeydown={(event) => event.key === 'Enter' && navigate()}
				placeholder="https://example.com"
				spellcheck="false"
			/>
			<a
				class="absolute top-1/2 right-1 z-10 grid h-5 w-5 -translate-y-1/2 place-items-center rounded-full text-xs text-gray-500 hover:bg-gray-200/60 dark:hover:bg-white/8"
				href={newTabUrl(urlInput) || undefined}
				target="_blank"
				rel="noopener noreferrer"
				aria-label={$t('port.openInNewTab')}
				use:tooltip={$t('port.openInNewTab')}>↗</a
			>
		</div>
	</div>
	{#if modeError}<div class="mode-error" title={modeError}>{modeError}</div>{/if}
	{#if loading}<div class="loading-track"><div class="loading-bar"></div></div>{/if}
	<div class="preview-content">
		{#if error}
			<div class="preview-error">
				<p class="error-title">{error}</p>
				<button class="error-retry" onclick={() => navigate()}>{$t('files.retry')}</button>
			</div>
		{:else if mode === 'chrome'}
			<ChromeBrowser
				bind:this={chromeEl}
				{sessionId}
				{active}
				onstate={(state) => {
					urlInput = state.url || urlInput;
					title = state.title || '';
					updateTabLabel(tabId, title);
					canGoBack = state.can_go_back;
					canGoForward = state.can_go_forward;
				}}
				onstatus={(status, message, nextMode) => {
					chromeStatus = status;
					loading = status === 'connecting';
					if (message) modeError = message;
					else if (status === 'playing' || status === 'view_only') modeError = '';
					if (nextMode === 'proxy') {
						mode = 'proxy';
						if (urlInput) frameSrc = browserFrameUrl(sessionId, urlInput);
					}
				}}
			/>
			{#if chromeStatus === 'connecting'}
				<div
					class="pointer-events-none absolute inset-0 z-10 flex items-center justify-center gap-2 bg-white/80 text-xs text-gray-500 dark:bg-black/80 dark:text-gray-400"
				>
					<Spinner size={14} />
					<span>{$t('common.loading')}</span>
				</div>
			{/if}
			{#if chromeStatus === 'view_only'}<div class="status-pill">{$t('browser.viewOnly')}</div>{/if}
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
	.mode-error {
		padding: 0.2rem 0.5rem;
		font-size: 0.6875rem;
		color: var(--color-red-600);
		background: color-mix(in srgb, var(--color-red-500) 8%, transparent);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.status-pill {
		position: absolute;
		top: 0.5rem;
		right: 0.5rem;
		padding: 0.2rem 0.45rem;
		border-radius: 999px;
		background: rgba(0, 0, 0, 0.65);
		color: white;
		font-size: 0.6875rem;
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
</style>
