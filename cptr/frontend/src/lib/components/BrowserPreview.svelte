<script lang="ts">
	import { onDestroy, onMount, tick } from 'svelte';
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
	import DropdownMenu from './DropdownMenu.svelte';
	import Spinner from './common/Spinner.svelte';
	import { t } from '$lib/i18n';

	interface Props {
		sessionId: string;
		groupId: string;
		tabId: string;
		initialUrl?: string;
		active?: boolean;
		onTabUpdate?: (label: string) => void;
		onOpenBrowser?: (url?: string) => void;
	}

	type DeviceMode = 'auto' | 'desktop' | 'mobile';
	type MobileViewport = { width: number; height: number };

	let {
		sessionId,
		groupId,
		tabId,
		initialUrl,
		active = true,
		onTabUpdate,
		onOpenBrowser
	}: Props = $props();
	let iframeEl: HTMLIFrameElement | undefined = $state();
	let chromeEl: ChromeBrowser | undefined = $state();
	let frameSrc = $state(browserBlankUrl(sessionId));
	let urlInput = $state(initialUrl ?? '');
	let title = $state('');
	let error = $state('');
	let modeError = $state('');
	let mode = $state<'proxy' | 'chrome'>('proxy');
	let chromeStatus = $state('');
	let canGoBack = $state(false);
	let canGoForward = $state(false);
	let chromeQuality = $state<'low' | 'balanced' | 'crisp' | null>(null);
	let chromeDeviceMode = $state<DeviceMode>('auto');
	let chromeMobileViewport = $state<MobileViewport | undefined>();
	let qualityMenuOpen = $state(false);
	let qualityMenuAnchor = $state<HTMLElement>();

	function updateLabel(label: string) {
		if (!label.trim()) return;
		if (onTabUpdate) onTabUpdate(label);
		else updateTabLabel(tabId, label);
	}

	function setChromeQuality(quality: 'low' | 'balanced' | 'crisp') {
		chromeEl?.setQuality(quality);
		chromeQuality = quality;
		qualityMenuOpen = false;
	}

	function setChromeDeviceMode(nextMode: DeviceMode) {
		chromeDeviceMode = nextMode;
		chromeEl?.setDeviceMode(nextMode);
	}

	function setChromeMobileDimension(key: keyof MobileViewport, value: number) {
		if (!Number.isFinite(value) || value <= 0) return;
		chromeMobileViewport = {
			...(chromeMobileViewport ?? { width: 390, height: 844 }),
			[key]: Math.round(value)
		};
		chromeEl?.setMobileViewport(chromeMobileViewport);
	}

	function setChromeMobileViewport(enabled: boolean) {
		chromeMobileViewport = enabled
			? (chromeMobileViewport ?? { width: 390, height: 844 })
			: undefined;
		chromeEl?.setMobileViewport(chromeMobileViewport);
	}

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
		if (mode === 'chrome') chromeEl?.reload();
		else iframeEl?.contentWindow?.location.reload();
	}

	function frameLoaded() {
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
			updateLabel(title);
			void updateBrowserSession(sessionId, urlInput, title).catch(() => {});
		}
		if (data?.type === 'cptr-browser-popup' && data.url) {
			if (onOpenBrowser) onOpenBrowser(data.url);
			else openBrowserTab(groupId, data.url);
		}
	}

	onMount(() => {
		window.addEventListener('message', receiveMessage);
		void getBrowserSession(sessionId)
			.then(async (session) => {
				const url = publicUrl(session.url || initialUrl || '');
				urlInput = url;
				title = session.title;
				updateLabel(title);
				mode = session.mode || 'proxy';
				if (mode === 'chrome') {
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
				else if (url && mode === 'chrome' && !session.url) {
					await tick();
					chromeEl?.navigate(url);
				}
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
		{#if mode === 'chrome' && chromeQuality}
			<button
				bind:this={qualityMenuAnchor}
				class="flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-700 dark:hover:bg-white/6 dark:hover:text-gray-300"
				aria-label={$t('admin.browserQuality')}
				use:tooltip={$t('admin.browserQuality')}
				onclick={() => (qualityMenuOpen = !qualityMenuOpen)}
			>
				<Icon name="three-dots" size={12} />
			</button>
		{/if}
	</div>
	{#if qualityMenuOpen && qualityMenuAnchor}
		<DropdownMenu
			items={[]}
			anchor={qualityMenuAnchor}
			align="end"
			onclose={() => (qualityMenuOpen = false)}
		>
			<div class="p-1 text-xs">
				{#each [{ value: 'low' as const, label: $t('admin.browserQualityLow') }, { value: 'balanced' as const, label: $t('admin.browserQualityBalanced') }, { value: 'crisp' as const, label: $t('admin.browserQualityCrisp') }] as item}
					<button
						class="flex h-6 w-full items-center rounded-lg px-2 text-left hover:bg-gray-100 dark:hover:bg-white/8 {chromeQuality ===
						item.value
							? 'font-medium text-gray-900 dark:text-white'
							: 'text-gray-500 dark:text-gray-400'}"
						onclick={() => setChromeQuality(item.value)}
					>
						<span class="flex-1">{item.label}</span>
						{#if chromeQuality === item.value}<Icon name="check" size={12} />{/if}
					</button>
				{/each}
				<div class="my-1 h-px bg-gray-200 dark:bg-white/8"></div>
				<div class="px-1 pb-1 pt-0.5 text-[0.625rem] text-gray-400 dark:text-gray-600">
					{$t('browser.device')}
				</div>
				<div class="flex gap-1">
					{#each [{ value: 'auto' as DeviceMode, label: $t('browser.deviceAuto'), icon: 'monitor' }, { value: 'desktop' as DeviceMode, label: $t('browser.deviceDesktop'), icon: 'monitor' }, { value: 'mobile' as DeviceMode, label: $t('browser.deviceMobile'), icon: 'phone' }] as item}
						<button
							class="flex h-7 flex-1 items-center justify-center gap-1 rounded-lg px-1.5 text-[0.625rem] transition-colors {chromeDeviceMode ===
							item.value
								? 'bg-gray-200/50 font-medium text-gray-900 dark:bg-white/8 dark:text-white'
								: 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'}"
							onclick={() => setChromeDeviceMode(item.value)}
						>
							<Icon name={item.icon} size={12} />
							{item.label}
						</button>
					{/each}
				</div>
				{#if chromeDeviceMode === 'mobile'}
					<label
						class="mt-1.5 flex items-center justify-between gap-2 px-1 text-[0.625rem] text-gray-500 dark:text-gray-400"
					>
						<span>{$t('browser.deviceFixedViewport')}</span>
						<input
							type="checkbox"
							checked={Boolean(chromeMobileViewport)}
							onchange={(event) => setChromeMobileViewport(event.currentTarget.checked)}
						/>
					</label>
					{#if chromeMobileViewport}
						<div
							class="mt-1.5 flex items-center gap-1 text-[0.625rem] text-gray-500 dark:text-gray-400"
						>
							<input
								type="number"
								min="1"
								value={chromeMobileViewport.width}
								aria-label={$t('browser.deviceWidth')}
								use:tooltip={$t('browser.deviceWidthHint')}
								onchange={(event) =>
									setChromeMobileDimension('width', event.currentTarget.valueAsNumber)}
								class="h-6 min-w-0 rounded-md border border-gray-200 bg-gray-100 px-1 text-center dark:border-white/8 dark:bg-white/6"
							/>
							<span>×</span>
							<input
								type="number"
								min="1"
								value={chromeMobileViewport.height}
								aria-label={$t('browser.deviceHeight')}
								use:tooltip={$t('browser.deviceHeightHint')}
								onchange={(event) =>
									setChromeMobileDimension('height', event.currentTarget.valueAsNumber)}
								class="h-6 min-w-0 rounded-md border border-gray-200 bg-gray-100 px-1 text-center dark:border-white/8 dark:bg-white/6"
							/>
						</div>
					{/if}
				{/if}
			</div>
		</DropdownMenu>
	{/if}
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
					updateLabel(title);
					canGoBack = state.can_go_back;
					canGoForward = state.can_go_forward;
				}}
				onstatus={(status, message, nextMode) => {
					chromeStatus = status;
					if (message) modeError = message;
					else if (status === 'playing') modeError = '';
					if (nextMode === 'proxy') {
						mode = 'proxy';
						chromeQuality = null;
						if (urlInput) frameSrc = browserFrameUrl(sessionId, urlInput);
					}
				}}
				onquality={(quality) => (chromeQuality = quality)}
				ondevicemode={(nextMode, viewport) => {
					chromeDeviceMode = nextMode;
					chromeMobileViewport = viewport;
				}}
			/>
			{#if chromeStatus === 'reconnecting'}
				<div
					class="pointer-events-none absolute inset-0 z-10 flex items-center justify-center gap-2 bg-white/80 text-xs text-gray-500 dark:bg-black/80 dark:text-gray-400"
				>
					<Spinner size={14} />
					<span>{$t('common.loading')}</span>
				</div>
			{:else if chromeStatus === 'lost'}
				<div
					class="absolute inset-0 z-10 flex flex-col items-center justify-center gap-1 bg-white/80 px-4 text-center text-xs text-gray-500 dark:bg-black/80 dark:text-gray-400"
				>
					<span class="font-medium">{$t('browser.connectionLost')}</span>
					{#if modeError}<span class="max-w-md opacity-75">{modeError}</span>{/if}
				</div>
			{/if}
		{:else}
			<iframe
				bind:this={iframeEl}
				src={frameSrc}
				title={title || $t('bar.newBrowser')}
				class="preview-iframe"
				onload={frameLoaded}
				onerror={() => {
					error = $t('port.cannotConnect');
				}}
			></iframe>
		{/if}
	</div>
</div>

<style>
	@reference "../../app.css";
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
		background: var(--app-bg);
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
</style>
