export type DiffLineType = 'added' | 'removed' | 'context';
export type DiffLine = { type: DiffLineType; content: string };
export type DiffHunk = { header: string; lines: DiffLine[] };
export type DiffFile = { path: string; hunks: DiffHunk[] };
export type NumberedDiffLine = DiffLine & { oldNumber: number | null; newNumber: number | null };
export type InlineDiffSegment = { text: string; changed: boolean };
export type InlineDiffLine = NumberedDiffLine & { segments: InlineDiffSegment[] };
export type DiffLineGroup<T extends { type: string }> = { type: T['type']; lines: T[] };
export type SplitDiffRow = { oldLine: InlineDiffLine | null; newLine: InlineDiffLine | null };
export type DiffStats = { additions: number; deletions: number };

export function countDiffStats(files: DiffFile[]): DiffStats {
	let additions = 0;
	let deletions = 0;
	for (const file of files) {
		for (const hunk of file.hunks) {
			for (const line of hunk.lines) {
				if (line.type === 'added') additions += 1;
				if (line.type === 'removed') deletions += 1;
			}
		}
	}
	return { additions, deletions };
}

export function languageForPath(path: string): string {
	const ext = path.slice(path.lastIndexOf('.')).toLowerCase();
	const byExt: Record<string, string> = {
		'.py': 'python',
		'.js': 'javascript',
		'.ts': 'typescript',
		'.jsx': 'jsx',
		'.tsx': 'tsx',
		'.svelte': 'svelte',
		'.css': 'css',
		'.scss': 'scss',
		'.html': 'html',
		'.json': 'json',
		'.xml': 'xml',
		'.yaml': 'yaml',
		'.yml': 'yaml',
		'.toml': 'toml',
		'.md': 'markdown',
		'.sh': 'bash',
		'.bash': 'bash',
		'.zsh': 'bash',
		'.rs': 'rust',
		'.go': 'go',
		'.java': 'java',
		'.c': 'c',
		'.h': 'c',
		'.cpp': 'cpp',
		'.hpp': 'cpp',
		'.rb': 'ruby',
		'.php': 'php',
		'.swift': 'swift',
		'.kt': 'kotlin',
		'.sql': 'sql',
		'.lua': 'lua',
		'.dockerfile': 'dockerfile',
		'.makefile': 'makefile'
	};
	return byExt[ext] ?? 'text';
}

export function numberDiffLines(hunk: DiffHunk): NumberedDiffLine[] {
	const match = hunk.header.match(/^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/);
	let oldNumber = match ? Number(match[1]) : 0;
	let newNumber = match ? Number(match[2]) : 0;

	return hunk.lines.map((line) => {
		if (line.type === 'added') return { ...line, oldNumber: null, newNumber: newNumber++ };
		if (line.type === 'removed') return { ...line, oldNumber: oldNumber++, newNumber: null };
		return { ...line, oldNumber: oldNumber++, newNumber: newNumber++ };
	});
}

export function groupDiffLines<T extends { type: string }>(lines: T[]): DiffLineGroup<T>[] {
	const groups: DiffLineGroup<T>[] = [];
	for (const line of lines) {
		const last = groups[groups.length - 1];
		if (last && last.type === line.type) last.lines.push(line);
		else groups.push({ type: line.type, lines: [line] });
	}
	return groups;
}

export function withInlineDiffSegments(lines: NumberedDiffLine[]): InlineDiffLine[] {
	const result: InlineDiffLine[] = [];
	let i = 0;

	while (i < lines.length) {
		const line = lines[i];
		if (line.type === 'context') {
			result.push({ ...line, segments: [{ text: line.content || ' ', changed: false }] });
			i += 1;
			continue;
		}

		const block: NumberedDiffLine[] = [];
		while (i < lines.length && lines[i].type !== 'context') {
			block.push(lines[i]);
			i += 1;
		}

		const removed = block.filter((item) => item.type === 'removed');
		const added = block.filter((item) => item.type === 'added');
		const removedSegments = removed.map((item, index) =>
			segmentsForPair(item.content, added[index]?.content, 'removed')
		);
		const addedSegments = added.map((item, index) =>
			segmentsForPair(removed[index]?.content, item.content, 'added')
		);

		for (const item of block) {
			const index =
				item.type === 'removed'
					? removed.indexOf(item)
					: item.type === 'added'
						? added.indexOf(item)
						: -1;
			const segments =
				item.type === 'removed'
					? removedSegments[index]
					: item.type === 'added'
						? addedSegments[index]
						: [{ text: item.content || ' ', changed: false }];
			result.push({ ...item, segments });
		}
	}

	return result;
}

export function splitDiffRows(lines: InlineDiffLine[]): SplitDiffRow[] {
	const rows: SplitDiffRow[] = [];
	let i = 0;

	while (i < lines.length) {
		const line = lines[i];
		if (line.type === 'context') {
			rows.push({ oldLine: line, newLine: line });
			i += 1;
			continue;
		}

		const block: InlineDiffLine[] = [];
		while (i < lines.length && lines[i].type !== 'context') {
			block.push(lines[i]);
			i += 1;
		}

		const removed = block.filter((item) => item.type === 'removed');
		const added = block.filter((item) => item.type === 'added');
		const count = Math.max(removed.length, added.length);
		for (let index = 0; index < count; index += 1) {
			rows.push({ oldLine: removed[index] ?? null, newLine: added[index] ?? null });
		}
	}

	return rows;
}

function segmentsForPair(
	oldText: string | undefined,
	newText: string | undefined,
	side: 'removed' | 'added'
): InlineDiffSegment[] {
	const text = side === 'removed' ? oldText : newText;
	if (text === undefined) return [];
	if (oldText === undefined || newText === undefined)
		return [{ text: text || ' ', changed: false }];
	if (oldText === newText) return [{ text: text || ' ', changed: false }];

	let prefix = 0;
	const maxPrefix = Math.min(oldText.length, newText.length);
	while (prefix < maxPrefix && oldText[prefix] === newText[prefix]) prefix += 1;

	let oldSuffix = oldText.length;
	let newSuffix = newText.length;
	while (
		oldSuffix > prefix &&
		newSuffix > prefix &&
		oldText[oldSuffix - 1] === newText[newSuffix - 1]
	) {
		oldSuffix -= 1;
		newSuffix -= 1;
	}

	const oldChangedLength = oldSuffix - prefix;
	const newChangedLength = newSuffix - prefix;
	const sharedLength = Math.max(
		oldText.length - oldChangedLength,
		newText.length - newChangedLength
	);
	const similarity = sharedLength / Math.max(oldText.length, newText.length, 1);
	const changedLength = side === 'removed' ? oldChangedLength : newChangedLength;
	if (similarity < 0.55 || changedLength / Math.max(text.length, 1) > 0.45) {
		return [{ text: text || ' ', changed: false }];
	}

	const end = side === 'removed' ? oldSuffix : newSuffix;
	const changed = text.slice(prefix, end);
	const tokenStart = changed.search(/[A-Za-z0-9_$]/);
	if (tokenStart < 0) return [{ text: text || ' ', changed: false }];

	const tokenEnd = changed.search(/[A-Za-z0-9_$][^A-Za-z0-9_$]*$/);
	const highlightStart = tokenStart >= 0 ? prefix + tokenStart : prefix;
	const highlightEnd = tokenEnd >= 0 ? prefix + tokenEnd + 1 : end;
	const segments = [
		{ text: text.slice(0, highlightStart), changed: false },
		{ text: text.slice(highlightStart, highlightEnd), changed: true },
		{ text: text.slice(highlightEnd), changed: false }
	].filter((segment) => segment.text.length > 0);

	return segments.length ? segments : [{ text: ' ', changed: false }];
}
