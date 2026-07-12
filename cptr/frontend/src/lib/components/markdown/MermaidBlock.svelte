<script lang="ts">
	import { t } from '$lib/i18n';

	let { code }: { code: string } = $props();

	let containerEl: HTMLDivElement | undefined = $state();
	let error = $state<string | null>(null);
	let rendered = $state(false);

	$effect(() => {
		if (!containerEl || rendered) return;
		const currentCode = code;

		(async () => {
			try {
				const mermaid = (await import('mermaid')).default;
				mermaid.initialize({
					startOnLoad: false,
					theme: document.documentElement.classList.contains('dark') ? 'dark' : 'default',
					securityLevel: 'strict',
					fontFamily: 'inherit'
				});

				const id = `mermaid-${Math.random().toString(36).slice(2, 9)}`;
				const { svg } = await mermaid.render(id, currentCode);

				if (containerEl) {
					containerEl.innerHTML = svg;
					rendered = true;
				}
			} catch (e: any) {
				error = e.message || $t('preview.diagramRenderError');
			}
		})();
	});
</script>

<div class="mermaid-block">
	{#if error}
		<div class="mermaid-error">
			<span class="mermaid-error-label">{$t('preview.diagramError')}</span>
			<pre class="mermaid-error-msg">{error}</pre>
			<pre class="mermaid-source">{code}</pre>
		</div>
	{:else}
		<div bind:this={containerEl} class="mermaid-container"></div>
	{/if}
</div>

<style>
	@reference "../../../app.css";

	.mermaid-block {
		margin: 0 0 0.75rem;
		border-radius: 0.5rem;
		overflow: hidden;
		border: 1px solid var(--app-border);
	}

	.mermaid-container {
		display: flex;
		justify-content: center;
		padding: 1rem;
		background: var(--app-hover);
		overflow-x: auto;
	}

	.mermaid-container :global(svg) {
		max-width: 100%;
		height: auto;
	}

	.mermaid-error {
		padding: 0.75rem 1rem;
		background: rgba(220, 38, 38, 0.04);
	}

	.mermaid-error-label {
		font-size: 0.6875rem;
		font-weight: 500;
		color: #dc2626;
	}

	.mermaid-error-msg {
		margin: 0.25rem 0 0.5rem;
		font-size: 0.75rem;
		color: #dc2626;
		white-space: pre-wrap;
		font-family: 'JetBrains Mono', 'Fira Code', ui-monospace, monospace;
	}

	.mermaid-source {
		margin: 0;
		padding: 0.5rem 0.75rem;
		font-size: 0.75rem;
		background: var(--app-hover);
		border-radius: 0.25rem;
		color: var(--app-fg-muted);
		font-family: 'JetBrains Mono', 'Fira Code', ui-monospace, monospace;
	}

</style>
