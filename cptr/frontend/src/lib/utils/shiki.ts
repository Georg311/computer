/** Shared Shiki highlighter singleton — avoids "10/20 instances created" warnings. */

import type { HighlighterCore } from 'shiki/core'

let highlighterPromise: Promise<HighlighterCore> | null = null

export async function getHighlighter(): Promise<HighlighterCore> {
	if (!highlighterPromise) {
		highlighterPromise = (async () => {
			const { createHighlighterCore } = await import('shiki/core')
			const { createOnigurumaEngine } = await import('shiki/engine/oniguruma')
			return createHighlighterCore({
				themes: [import('shiki/themes/github-light.mjs'), import('shiki/themes/github-dark.mjs')],
				langs: [
					import('shiki/langs/javascript.mjs'),
					import('shiki/langs/typescript.mjs'),
					import('shiki/langs/python.mjs'),
					import('shiki/langs/bash.mjs'),
					import('shiki/langs/shell.mjs'),
					import('shiki/langs/json.mjs'),
					import('shiki/langs/html.mjs'),
					import('shiki/langs/css.mjs'),
					import('shiki/langs/markdown.mjs'),
					import('shiki/langs/yaml.mjs'),
					import('shiki/langs/toml.mjs'),
					import('shiki/langs/rust.mjs'),
					import('shiki/langs/go.mjs'),
					import('shiki/langs/c.mjs'),
					import('shiki/langs/cpp.mjs'),
					import('shiki/langs/java.mjs'),
					import('shiki/langs/sql.mjs'),
					import('shiki/langs/svelte.mjs'),
					import('shiki/langs/dockerfile.mjs'),
					import('shiki/langs/xml.mjs'),
					import('shiki/langs/ruby.mjs'),
					import('shiki/langs/php.mjs'),
					import('shiki/langs/swift.mjs'),
					import('shiki/langs/kotlin.mjs'),
					import('shiki/langs/lua.mjs'),
					import('shiki/langs/tsx.mjs'),
					import('shiki/langs/jsx.mjs'),
					import('shiki/langs/scss.mjs'),
					import('shiki/langs/graphql.mjs'),
					import('shiki/langs/makefile.mjs'),
				],
				engine: createOnigurumaEngine(import('shiki/wasm')),
			})
		})()
	}
	return highlighterPromise
}
