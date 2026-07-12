<script lang="ts">
	import type { Editor } from '@tiptap/core';
	import Icon from '../Icon.svelte';
	import { tooltip } from '$lib/tooltip';
	import { t } from '$lib/i18n';

	interface Props {
		editor: Editor;
	}

	let { editor }: Props = $props();

	// Reactive state: recompute on every editor transaction
	let active = $state({
		bold: false,
		italic: false,
		underline: false,
		strike: false,
		code: false,
		highlight: false,
		h1: false,
		h2: false,
		h3: false,
		bulletList: false,
		orderedList: false,
		taskList: false,
		blockquote: false,
		codeBlock: false
	});

	$effect(() => {
		if (!editor) return;

		const update = () => {
			active = {
				bold: editor.isActive('bold'),
				italic: editor.isActive('italic'),
				underline: editor.isActive('underline'),
				strike: editor.isActive('strike'),
				code: editor.isActive('code'),
				highlight: editor.isActive('highlight'),
				h1: editor.isActive('heading', { level: 1 }),
				h2: editor.isActive('heading', { level: 2 }),
				h3: editor.isActive('heading', { level: 3 }),
				bulletList: editor.isActive('bulletList'),
				orderedList: editor.isActive('orderedList'),
				taskList: editor.isActive('taskList'),
				blockquote: editor.isActive('blockquote'),
				codeBlock: editor.isActive('codeBlock')
			};
		};

		editor.on('selectionUpdate', update);
		editor.on('transaction', update);
		update();

		return () => {
			editor.off('selectionUpdate', update);
			editor.off('transaction', update);
		};
	});

	function cmd(action: () => boolean) {
		return () => {
			action();
			editor?.chain().focus().run();
		};
	}
</script>

<!-- Desktop: top bar. Mobile: bottom bar above keyboard -->
<div class="editor-toolbar">
	<div class="toolbar-scroll">
		<!-- Text formatting -->
		<button
			class="tb-btn"
			class:active={active.bold}
			onclick={() => editor.chain().focus().toggleBold().run()}
			use:tooltip={$t('markdown.boldShortcut')}><strong>B</strong></button
		>

		<button
			class="tb-btn"
			class:active={active.italic}
			onclick={() => editor.chain().focus().toggleItalic().run()}
			use:tooltip={$t('markdown.italicShortcut')}><em>I</em></button
		>

		<button
			class="tb-btn"
			class:active={active.underline}
			onclick={() => editor.chain().focus().toggleUnderline().run()}
			use:tooltip={$t('markdown.underlineShortcut')}><u>U</u></button
		>

		<button
			class="tb-btn"
			class:active={active.strike}
			onclick={() => editor.chain().focus().toggleStrike().run()}
			use:tooltip={$t('markdown.strikethrough')}><s>S</s></button
		>

		<button
			class="tb-btn"
			class:active={active.code}
			onclick={() => editor.chain().focus().toggleCode().run()}
			use:tooltip={$t('markdown.inlineCode')}><Icon name="code" size={12} /></button
		>

		<button
			class="tb-btn"
			class:active={active.highlight}
			onclick={() => editor.chain().focus().toggleHighlight().run()}
			use:tooltip={$t('markdown.highlight')}><span class="highlight-icon">H</span></button
		>

		<span class="tb-divider"></span>

		<!-- Headings -->
		<button
			class="tb-btn heading-btn"
			class:active={active.h1}
			onclick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}
			use:tooltip={$t('markdown.heading1')}>H1</button
		>

		<button
			class="tb-btn heading-btn"
			class:active={active.h2}
			onclick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
			use:tooltip={$t('markdown.heading2')}>H2</button
		>

		<button
			class="tb-btn heading-btn"
			class:active={active.h3}
			onclick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}
			use:tooltip={$t('markdown.heading3')}>H3</button
		>

		<span class="tb-divider"></span>

		<!-- Lists -->
		<button
			class="tb-btn"
			class:active={active.bulletList}
			onclick={() => editor.chain().focus().toggleBulletList().run()}
			use:tooltip={$t('markdown.bulletList')}><Icon name="list" size={12} /></button
		>

		<button
			class="tb-btn"
			class:active={active.orderedList}
			onclick={() => editor.chain().focus().toggleOrderedList().run()}
			use:tooltip={$t('markdown.numberedList')}><Icon name="list-ordered" size={12} /></button
		>

		<button
			class="tb-btn"
			class:active={active.taskList}
			onclick={() => editor.chain().focus().toggleTaskList().run()}
			use:tooltip={$t('markdown.taskList')}><Icon name="check-square" size={12} /></button
		>

		<span class="tb-divider"></span>

		<!-- Block elements -->
		<button
			class="tb-btn"
			class:active={active.blockquote}
			onclick={() => editor.chain().focus().toggleBlockquote().run()}
			use:tooltip={$t('markdown.quote')}><Icon name="quote" size={12} /></button
		>

		<button
			class="tb-btn"
			class:active={active.codeBlock}
			onclick={() => editor.chain().focus().toggleCodeBlock().run()}
			use:tooltip={$t('markdown.codeBlock')}>{'{ }'}</button
		>

		<button
			class="tb-btn"
			onclick={() => editor.chain().focus().setHorizontalRule().run()}
			use:tooltip={$t('markdown.horizontalRule')}>──</button
		>

		<span class="tb-divider"></span>

		<!-- Table -->
		<button
			class="tb-btn"
			onclick={() =>
				editor.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()}
			use:tooltip={$t('markdown.insertTable')}><Icon name="table" size={12} /></button
		>

		<!-- Undo/Redo -->
		<span class="tb-divider"></span>

		<button
			class="tb-btn"
			onclick={() => editor.chain().focus().undo().run()}
			disabled={!editor.can().undo()}
			use:tooltip={$t('markdown.undoShortcut')}><Icon name="undo" size={12} /></button
		>

		<button
			class="tb-btn"
			onclick={() => editor.chain().focus().redo().run()}
			disabled={!editor.can().redo()}
			use:tooltip={$t('markdown.redoShortcut')}><Icon name="redo" size={12} /></button
		>
	</div>
</div>

<style>
	@reference "../../../app.css";

	.editor-toolbar {
		display: flex;
		align-items: center;
		height: 2.25rem;
		padding: 0 0.5rem;
		border-bottom: 1px solid var(--app-border);
		background: var(--app-bg);
		flex-shrink: 0;
		overflow: hidden;
	}

	.toolbar-scroll {
		display: flex;
		align-items: center;
		gap: 0.0625rem;
		overflow-x: auto;
		overflow-y: hidden;
		scrollbar-width: none;
		-ms-overflow-style: none;
		-webkit-overflow-scrolling: touch;
	}

	.toolbar-scroll::-webkit-scrollbar {
		display: none;
	}

	.tb-btn {
		display: flex;
		align-items: center;
		justify-content: center;
		min-width: 1.75rem;
		height: 1.75rem;
		padding: 0 0.375rem;
		border: none;
		border-radius: 0.3125rem;
		background: transparent;
		color: var(--app-fg-muted);
		font-size: 0.75rem;
		font-weight: 500;
		cursor: pointer;
		transition: all 0.1s;
		white-space: nowrap;
		flex-shrink: 0;
	}

	.tb-btn:hover {
		background: var(--app-hover);
		color: var(--app-fg);
	}

	.tb-btn.active {
		background: var(--app-active);
		color: var(--app-fg);
	}

	.tb-btn:disabled {
		opacity: 0.3;
		cursor: default;
	}

	.heading-btn {
		font-size: 0.6875rem;
		font-weight: 700;
		font-family: inherit;
	}

	.tb-divider {
		width: 1px;
		height: 1rem;
		background: var(--app-divider);
		margin: 0 0.25rem;
		flex-shrink: 0;
	}

	.highlight-icon {
		background: rgba(255, 213, 79, 0.4);
		border-radius: 0.125rem;
		padding: 0 0.1875rem;
		font-weight: 700;
		font-size: 0.6875rem;
	}

	/* ── Mobile: pin to bottom above keyboard ────── */
	@media (max-width: 767px) {
		.editor-toolbar {
			position: fixed;
			bottom: 0;
			left: 0;
			right: 0;
			z-index: 60;
			height: 2.75rem;
			padding: 0 0.75rem;
			border-bottom: none;
			border-top: 1px solid var(--color-gray-200);
			padding-bottom: env(safe-area-inset-bottom, 0);
		}

		.editor-toolbar {
			border-top-color: var(--app-border);
			border-bottom: none;
		}

		.tb-btn {
			min-width: 2.25rem;
			height: 2.25rem;
			font-size: 0.8125rem;
		}
	}
</style>
