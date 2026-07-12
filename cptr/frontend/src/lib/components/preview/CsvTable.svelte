<script lang="ts">
	interface Props {
		content: string;
		separator?: string;
	}

	let { content, separator = ',' }: Props = $props();

	let parsed = $derived(() => {
		const lines = content.split('\n').filter((l) => l.trim());
		if (lines.length === 0) return { headers: [], rows: [] };

		// Simple CSV parse (handles quoted fields)
		function parseLine(line: string): string[] {
			const result: string[] = [];
			let current = '';
			let inQuotes = false;
			for (let i = 0; i < line.length; i++) {
				const ch = line[i];
				if (ch === '"') {
					if (inQuotes && line[i + 1] === '"') {
						current += '"';
						i++;
					} else {
						inQuotes = !inQuotes;
					}
				} else if (ch === separator && !inQuotes) {
					result.push(current.trim());
					current = '';
				} else {
					current += ch;
				}
			}
			result.push(current.trim());
			return result;
		}

		const headers = parseLine(lines[0]);
		const rows = lines.slice(1).map((l) => parseLine(l));
		return { headers, rows };
	});
</script>

<div class="csv-container">
	<table>
		<thead>
			<tr>
				<th class="row-num">#</th>
				{#each parsed().headers as header}
					<th>{header}</th>
				{/each}
			</tr>
		</thead>
		<tbody>
			{#each parsed().rows as row, i}
				<tr>
					<td class="row-num">{i + 1}</td>
					{#each row as cell}
						<td>{cell}</td>
					{/each}
				</tr>
			{/each}
		</tbody>
	</table>
</div>

<style>
	@reference "../../../app.css";

	.csv-container {
		width: 100%;
		height: 100%;
		overflow: auto;
	}

	table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.78125rem;
		font-family: var(--font-mono);
		white-space: nowrap;
	}

	thead {
		position: sticky;
		top: 0;
		z-index: 2;
	}

	th {
		background: var(--app-hover);
		color: var(--app-fg-muted);
		font-weight: 600;
		font-size: 0.6875rem;
		text-transform: uppercase;
		letter-spacing: 0.03em;
		padding: 0.375rem 0.75rem;
		text-align: left;
		border-bottom: 1px solid var(--app-border);
	}

	td {
		padding: 0.25rem 0.75rem;
		color: var(--app-fg);
		border-bottom: 1px solid var(--app-divider);
	}

	tbody tr:hover td {
		background: var(--app-hover);
	}

	/* Row numbers */
	.row-num {
		color: var(--app-fg-subtle);
		font-size: 0.6875rem;
		text-align: right;
		padding-right: 0.5rem;
		padding-left: 0.5rem;
		user-select: none;
		min-width: 2rem;
		border-right: 1px solid var(--app-divider);
	}

	thead .row-num {
		border-right-color: var(--app-border);
	}
</style>
