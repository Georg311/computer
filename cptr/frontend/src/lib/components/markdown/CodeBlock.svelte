<script lang="ts">
	import { t } from '$lib/i18n';
	import { getHighlighter } from '$lib/utils/shiki';


	interface Props {
		language: string;
		code: string;
		/** Optional diff-style callbacks for chat tool approval */
		onapply?: ((code: string) => void) | undefined;
		onreject?: (() => void) | undefined;
	}

	let { language, code, onapply, onreject }: Props = $props();

	let codeEl: HTMLElement | undefined = $state();
	let copied = $state(false);

	// Detect diff blocks
	let isDiff = $derived(language === 'diff');

	// Parse diff lines for coloring
	let diffLines = $derived.by(() => {
		if (!isDiff) return [];
		return code.split('\n').map((line) => ({
			text: line,
			type: line.startsWith('+')
				? ('add' as const)
				: line.startsWith('-')
					? ('del' as const)
					: line.startsWith('@@')
						? ('range' as const)
						: ('ctx' as const)
		}));
	});


	// Highlight non-diff code: reactive so it re-runs on prop changes (streaming)
	$effect(() => {
		if (isDiff || !codeEl) return;
		const currentCode = code;
		const currentLang = language;

		(async () => {
			try {
				const hl = await getHighlighter();
				if (!codeEl || currentCode !== code) return;

				const lang =
					currentLang && hl.getLoadedLanguages().includes(currentLang) ? currentLang : 'text';

				const html = hl.codeToHtml(currentCode, {
					lang,
					themes: { light: 'github-light', dark: 'github-dark' },
					defaultColor: false // use CSS variables for theme switching
				});

				// Shiki wraps in <pre style="--shiki-light:...;--shiki-dark:..."><code>...</code></pre>
				// We extract the <code> innerHTML but must also transfer the CSS vars
				// from <pre> onto our own <code> so base-color vars resolve.
				const tmp = document.createElement('div');
				tmp.innerHTML = html;
				const shikiPre = tmp.querySelector('pre');
				const shikiCode = tmp.querySelector('code');
				if (shikiCode && codeEl) {
					codeEl.innerHTML = shikiCode.innerHTML;
					// Copy --shiki-* CSS vars from the discarded <pre> onto our <code>
					if (shikiPre) {
						const preStyle = shikiPre.getAttribute('style') || '';
						const vars = preStyle.match(/--shiki[\w-]*:[^;]+/g) || [];
						vars.forEach((v) => {
							const [name, val] = v.split(':');
							if (name && val) codeEl!.style.setProperty(name.trim(), val.trim());
						});
					}
				}
			} catch {
				// Fallback: just show plain text
			}
		})();
	});

	function handleCopy() {
		navigator.clipboard.writeText(code);
		copied = true;
		setTimeout(() => {
			copied = false;
		}, 2000);
	}
</script>

<div
	class="not-prose rounded-2xl overflow-hidden bg-black/[0.03] dark:bg-white/[0.03] border border-black/[0.06] dark:border-white/[0.06]"
>
	<div class="flex items-center justify-between h-[1.875rem] px-2.5">
		<span class="text-[0.6875rem] font-medium text-gray-500 lowercase">{language || 'text'}</span>
		<div class="flex items-center gap-1">
			{#if isDiff && onapply}
				<button
					class="text-[0.6875rem] px-2 py-0.5 rounded text-green-600 hover:bg-green-600/10 transition-all duration-100"
					onclick={() => onapply?.(code)}>{$t('common.apply')}</button
				>
				<button
					class="text-[0.6875rem] px-2 py-0.5 rounded text-red-600 hover:bg-red-600/10 transition-all duration-100"
					onclick={() => onreject?.()}>{$t('common.reject')}</button
				>
			{/if}
			<button
				class="text-[0.6875rem] px-2 py-0.5 rounded text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 hover:bg-gray-200 dark:hover:bg-white/[0.08] transition-all duration-100"
				onclick={handleCopy}
			>
				{copied ? '✓' : $t('common.copy')}
			</button>
		</div>
	</div>

	{#if isDiff}
		<pre
			class="!m-0 !pb-3 !px-4 overflow-x-auto text-[0.8125rem] leading-normal !bg-transparent font-mono"><code
				>{#each diffLines as line}<span class="diff-line diff-{line.type}"
						>{line.text}
</span>{/each}</code
			></pre>
	{:else}
		<pre
			class="!m-0 !pb-3 !px-4 overflow-x-auto text-[0.8125rem] leading-normal !bg-transparent text-[#24292e] dark:text-[#e1e4e8] font-mono"><code
				class="font-[inherit]"
				bind:this={codeEl}>{code}</code
			></pre>
	{/if}
</div>

<style>
	@reference "../../../app.css";

	/* ── Shiki dual-theme: switch via CSS variables ── */

	pre :global(span) {
		color: var(--shiki-light);
	}

	:global(.dark) pre :global(span) {
		color: var(--shiki-dark);
	}

	/* ── Diff line coloring ──────────────────────── */

	.diff-line {
		display: block;
	}

	.diff-line.diff-add {
		background: rgba(22, 163, 74, 0.1);
		color: #16a34a;
	}

	:global(.dark) .diff-line.diff-add {
		background: rgba(34, 197, 94, 0.1);
		color: #4ade80;
	}

	.diff-line.diff-del {
		background: rgba(220, 38, 38, 0.08);
		color: #dc2626;
	}

	:global(.dark) .diff-line.diff-del {
		background: rgba(248, 113, 113, 0.1);
		color: #f87171;
	}

	.diff-line.diff-range {
		color: #8b5cf6;
	}

	:global(.dark) .diff-line.diff-range {
		color: #a78bfa;
	}
</style>
