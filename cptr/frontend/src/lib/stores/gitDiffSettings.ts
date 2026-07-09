import { writable } from 'svelte/store';

const HIDE_WHITESPACE_KEY = 'gitDiff:hideWhitespace';
const DISPLAY_MODE_KEY = 'gitDiff:displayMode';
export type DiffDisplayMode = 'unified' | 'split';

function persistedBoolean(key: string, fallback: boolean) {
	const initial =
		typeof localStorage !== 'undefined' ? localStorage.getItem(key) === 'true' : fallback;
	const store = writable(initial);
	store.subscribe((value) => {
		if (typeof localStorage !== 'undefined') localStorage.setItem(key, String(value));
	});
	return store;
}

export const hideWhitespaceChanges = persistedBoolean(HIDE_WHITESPACE_KEY, false);

const initialDisplayMode =
	typeof localStorage !== 'undefined'
		? localStorage.getItem(DISPLAY_MODE_KEY) === 'split'
			? 'split'
			: 'unified'
		: 'unified';

export const diffDisplayMode = writable<DiffDisplayMode>(initialDisplayMode);
diffDisplayMode.subscribe((value) => {
	if (typeof localStorage !== 'undefined') localStorage.setItem(DISPLAY_MODE_KEY, value);
});
