<script lang="ts">
	import { activeTab } from '$lib/stores';
	import { i18next } from '$lib/i18n';

	let visible = $state(false);
	let ctrlHeld = $state(false);
	let dictating = $state(false);
	let dictationRecognition: any = null;
	let touchHandled = false;

	// Show on touch devices when terminal is active
	function isTouchDevice() {
		return 'ontouchstart' in window || navigator.maxTouchPoints > 0;
	}

	$effect(() => {
		if (typeof window === 'undefined') return;

		if (isTouchDevice() && $activeTab?.type === 'terminal') {
			visible = true;
			return;
		}

		if (!window.visualViewport) return;
		const check = () => {
			const heightDiff = window.innerHeight - window.visualViewport!.height;
			visible = heightDiff > 150 && $activeTab?.type === 'terminal';
		};
		window.visualViewport.addEventListener('resize', check);
		return () => window.visualViewport?.removeEventListener('resize', check);
	});

	// When Ctrl is held, intercept the NEXT keypress before xterm gets it
	$effect(() => {
		if (!ctrlHeld) return;

		function interceptKey(e: KeyboardEvent) {
			if (e.key.length === 1 && !e.ctrlKey && !e.metaKey) {
				e.preventDefault();
				e.stopPropagation();
				e.stopImmediatePropagation();
				const code = String.fromCharCode(e.key.toUpperCase().charCodeAt(0) - 64);
				window.dispatchEvent(new CustomEvent('cptr:terminal-input', { detail: code }));
				ctrlHeld = false;
			}
		}

		// Use capture phase to get the event before xterm
		window.addEventListener('keydown', interceptKey, true);
		return () => window.removeEventListener('keydown', interceptKey, true);
	});

	function sendKey(key: string) {
		window.dispatchEvent(new CustomEvent('cptr:terminal-input', { detail: key }));
	}

	function startDictation() {
		const SpeechRecognition =
			(window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
		if (!SpeechRecognition) {
			alert(i18next.t('chat.dictate.unsupported'));
			return;
		}

		const recognition = new SpeechRecognition();
		dictationRecognition = recognition;
		recognition.continuous = true;
		recognition.interimResults = false;
		recognition.lang = navigator.language || 'en-US';

		recognition.onresult = (event: any) => {
			let text = '';
			for (let i = event.resultIndex; i < event.results.length; i++) {
				const result = event.results[i];
				if (result?.isFinal) text += ` ${result[0]?.transcript || ''}`;
			}
			text = text.trim();
			if (text) sendKey(text);
		};

		recognition.onerror = () => {
			dictating = false;
			dictationRecognition = null;
		};

		recognition.onend = () => {
			dictating = false;
			dictationRecognition = null;
		};

		try {
			recognition.start();
			dictating = true;
		} catch {
			dictating = false;
			dictationRecognition = null;
		}
	}

	function stopDictation() {
		const recognition = dictationRecognition;
		dictationRecognition = null;
		dictating = false;
		try {
			recognition?.stop();
		} catch {}
	}

	function toggleDictation() {
		if (dictating) stopDictation();
		else startDictation();
	}

	function toggleCtrl() {
		ctrlHeld = !ctrlHeld;
	}

	$effect(() => {
		if (!visible && dictating) stopDictation();
	});

	$effect(() => {
		return () => stopDictation();
	});

	const keys = [
		{ label: 'Tab', value: '\t' },
		{ label: 'Esc', value: '\x1b' },
		{ label: 'Ctrl', value: '__ctrl__' },
		{ label: '↑', value: '\x1b[A' },
		{ label: '↓', value: '\x1b[B' },
		{ label: '←', value: '\x1b[D' },
		{ label: '→', value: '\x1b[C' },
		{ label: '|', value: '|' },
		{ label: '~', value: '~' },
		{ label: '/', value: '/' },
		{ label: '-', value: '-' },
		{ label: '_', value: '_' }
	];
</script>

{#if visible}
	<div class="shortcut-bar">
		<button
			class="key inline-flex items-center justify-center"
			class:active={dictating}
			aria-label={i18next.t('terminal.dictateInput')}
			title={i18next.t('terminal.dictateInput')}
			onmousedown={(e) => e.preventDefault()}
			ontouchstart={(e) => {
				e.preventDefault();
				touchHandled = true;
				toggleDictation();
			}}
			onclick={() => {
				if (touchHandled) {
					touchHandled = false;
					return;
				}
				toggleDictation();
			}}
		>
			<svg
				class="size-3.5"
				viewBox="0 0 24 24"
				fill="none"
				stroke="currentColor"
				stroke-width="1.75"
				stroke-linecap="round"
				stroke-linejoin="round"
			>
				<rect x="9" y="2" width="6" height="12" rx="3" />
				<path d="M5 10a7 7 0 0 0 14 0" />
				<line x1="12" y1="19" x2="12" y2="22" />
				<line x1="8" y1="22" x2="16" y2="22" />
			</svg>
		</button>
		{#each keys as key}
			{#if key.value === '__ctrl__'}
				<button
					class="key"
					class:active={ctrlHeld}
					onmousedown={(e) => e.preventDefault()}
					ontouchstart={(e) => {
						e.preventDefault();
						touchHandled = true;
						toggleCtrl();
					}}
					onclick={() => {
						if (touchHandled) {
							touchHandled = false;
							return;
						}
						toggleCtrl();
					}}>{key.label}</button
				>
			{:else}
				<button
					class="key"
					onmousedown={(e) => e.preventDefault()}
					ontouchstart={(e) => {
						e.preventDefault();
						touchHandled = true;
						sendKey(key.value);
					}}
					onclick={() => {
						if (touchHandled) {
							touchHandled = false;
							return;
						}
						sendKey(key.value);
					}}>{key.label}</button
				>
			{/if}
		{/each}
	</div>
{/if}

<style>
	@reference "../../app.css";

	.shortcut-bar {
		display: flex;
		align-items: center;
		gap: 0.25rem;
		padding: 0.25rem 0.5rem;
		background: var(--app-bg);
		border-top: 1px solid var(--app-border);
		overflow-x: auto;
		flex-shrink: 0;
		scrollbar-width: none;
	}

	.shortcut-bar::-webkit-scrollbar {
		display: none;
	}

	.key {
		padding: 0.25rem 0.625rem;
		font-size: 0.75rem;
		font-family: var(--font-mono);
		font-weight: 500;
		border-radius: 0.3125rem;
		color: var(--app-fg-muted);
		background: var(--app-hover);
		white-space: nowrap;
		flex-shrink: 0;
		transition: all 0.1s ease;
		min-width: 2rem;
		text-align: center;
		-webkit-tap-highlight-color: transparent;
	}

	.key:active {
		transform: scale(0.95);
	}

	.key.active {
		background: var(--app-fg);
		color: var(--app-bg);
	}
</style>
