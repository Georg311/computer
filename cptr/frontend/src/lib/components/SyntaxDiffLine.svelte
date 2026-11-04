<script module lang="ts">

	type HighlightToken = {
		content: string;
		offset: number;
		variants?: {
			light?: { color?: string };
			dark?: { color?: string };
		};
	};

	const tokenCache = new Map<string, HighlightToken[]>();


<script lang="ts">
	import type { DiffLineType, InlineDiffSegment } from '$lib/utils/diff';
	import { getHighlighter } from '$lib/utils/shiki';

	interface Props {
		type: DiffLineType;
		content: string;
		segments: InlineDiffSegment[];
		language: string;
		wrap?: boolean;
		class?: string;
	}

	type RenderSegment = InlineDiffSegment & {
		light?: string;
		dark?: string;
	};

	let { type, content, segments, language, wrap = false, class: className = '' }: Props = $props();
	let renderedSegments = $state<RenderSegment[] | null>(null);

	$effect(() => {
		const currentContent = content;
		const currentSegments = segments;
		const currentLanguage = language;

		(async () => {
			if (!currentLanguage || currentLanguage === 'text') {
				renderedSegments = null;
				return;
			}

			try {
				const key = `${currentLanguage}\0${currentContent}`;
				let tokens = tokenCache.get(key);
				if (!tokens) {
					const highlighter = await getHighlighter();
					if (!highlighter.getLoadedLanguages().includes(currentLanguage)) {
						renderedSegments = null;
						return;
					}
					const tokenLines = highlighter.codeToTokensWithThemes(currentContent, {
						lang: currentLanguage,
						themes: { light: 'github-light', dark: 'github-dark' }
					}) as HighlightToken[][];
					tokens = tokenLines[0] ?? [];
					tokenCache.set(key, tokens);
				}
				if (
					currentContent !== content ||
					currentSegments !== segments ||
					currentLanguage !== language
				) {
					return;
				}
				renderedSegments = mergeTokensWithSegments(tokens, currentSegments);
			} catch {
				renderedSegments = null;
			}
		})();
	});

	function mergeTokensWithSegments(
		tokens: HighlightToken[],
		diffSegments: InlineDiffSegment[]
	): RenderSegment[] {
		const ranges: Array<{ start: number; end: number; changed: boolean }> = [];
		let offset = 0;
		for (const segment of diffSegments) {
			ranges.push({ start: offset, end: offset + segment.text.length, changed: segment.changed });
			offset += segment.text.length;
		}

		const merged: RenderSegment[] = [];
		for (const token of tokens) {
			const tokenStart = token.offset;
			const tokenEnd = token.offset + token.content.length;
			for (const range of ranges) {
				const start = Math.max(tokenStart, range.start);
				const end = Math.min(tokenEnd, range.end);
				if (start >= end) continue;
				merged.push({
					text: token.content.slice(start - tokenStart, end - tokenStart),
					changed: range.changed,
					light: token.variants?.light?.color,
					dark: token.variants?.dark?.color
				});
			}
		}

		return merged.length ? merged : diffSegments;
	}

	function inlineSegmentClass(type: DiffLineType, changed: boolean): string {
		if (!changed) return '';
		if (type === 'added') return 'inline-change inline-added';
		if (type === 'removed') return 'inline-change inline-removed';
		return '';
	}

	function escapeHtml(text: string): string {
		return text
			.replaceAll('&', '&amp;')
			.replaceAll('<', '&lt;')
			.replaceAll('>', '&gt;')
			.replaceAll('"', '&quot;');
	}

	function htmlForSegments(type: DiffLineType, segments: RenderSegment[]): string {
		return segments
			.map((segment) => {
				const classes = inlineSegmentClass(type, segment.changed);
				const styles = [
					segment.light ? `--diff-token-light: ${segment.light}` : '',
					segment.dark ? `--diff-token-dark: ${segment.dark}` : ''
				]
					.filter(Boolean)
					.join('; ');
				const classAttr = classes ? ` class="${classes}"` : '';
				const styleAttr = styles ? ` style="${styles}"` : '';
				return `<span${classAttr}${styleAttr}>${escapeHtml(segment.text)}</span>`;
			})
			.join('');
	}

	const fallbackSegments = $derived(renderedSegments ?? segments);
	const html = $derived(htmlForSegments(type, fallbackSegments));
</script>

<code
	class="syntax-diff-line block px-2 {wrap
		? 'whitespace-pre-wrap break-words'
		: 'whitespace-pre'} {className}">{@html html}</code
>

<style>
	.syntax-diff-line :global(span) {
		color: var(--diff-token-light, inherit);
	}

	:global(.dark) .syntax-diff-line :global(span) {
		color: var(--diff-token-dark, inherit);
	}

	.syntax-diff-line :global(.inline-change) {
		border-radius: 0.125rem;
		box-decoration-break: clone;
		-webkit-box-decoration-break: clone;
		font-weight: 700;
		padding: 0.0625rem 0.125rem;
	}

	.syntax-diff-line :global(.inline-added) {
		background: rgba(22, 163, 74, 0.38);
		box-shadow: inset 0 -0.125rem 0 rgba(21, 128, 61, 0.42);
	}

	.syntax-diff-line :global(.inline-removed) {
		background: rgba(220, 38, 38, 0.32);
		box-shadow: inset 0 -0.125rem 0 rgba(185, 28, 28, 0.38);
	}

	:global(.dark) .syntax-diff-line :global(.inline-added) {
		background: rgba(34, 197, 94, 0.42);
		box-shadow: inset 0 -0.125rem 0 rgba(134, 239, 172, 0.5);
	}

	:global(.dark) .syntax-diff-line :global(.inline-removed) {
		background: rgba(248, 113, 113, 0.4);
		box-shadow: inset 0 -0.125rem 0 rgba(252, 165, 165, 0.48);
	}
</style>
