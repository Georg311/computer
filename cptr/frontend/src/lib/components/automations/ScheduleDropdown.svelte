<script lang="ts">
	/**
	 * RRULE schedule builder dropdown.
	 * Uses fixed positioning so it's never clipped by ancestor overflow.
	 */
	import { t } from '$lib/i18n';

	interface Props {
		rrule: string;
		onchange?: (rrule: string) => void;
	}

	let { rrule = $bindable(), onchange }: Props = $props();

	type Frequency = 'ONCE' | 'HOURLY' | 'DAILY' | 'WEEKLY' | 'MONTHLY' | 'CUSTOM';

	const FREQUENCIES: { key: Frequency; labelKey: string }[] = [
		{ key: 'ONCE', labelKey: 'automations.once' },
		{ key: 'HOURLY', labelKey: 'automations.hourly' },
		{ key: 'DAILY', labelKey: 'automations.daily' },
		{ key: 'WEEKLY', labelKey: 'automations.weekly' },
		{ key: 'MONTHLY', labelKey: 'automations.monthly' },
		{ key: 'CUSTOM', labelKey: 'automations.custom' }
	];

	const DAYS = [
		{ key: 'MO', labelKey: 'automations.dayMo' },
		{ key: 'TU', labelKey: 'automations.dayTu' },
		{ key: 'WE', labelKey: 'automations.dayWe' },
		{ key: 'TH', labelKey: 'automations.dayTh' },
		{ key: 'FR', labelKey: 'automations.dayFr' },
		{ key: 'SA', labelKey: 'automations.daySa' },
		{ key: 'SU', labelKey: 'automations.daySu' }
	];

	let frequency = $state<Frequency>('DAILY');
	let hour = $state(9);
	let minute = $state(0);
	let selectedDays = $state<string[]>([]);
	let monthDay = $state(1);
	let onceDate = $state('');
	let onceTime = $state('09:00');
	let customRrule = $state('');
	let showDropdown = $state(false);

	// Fixed positioning
	let triggerEl: HTMLButtonElement | undefined = $state();
	let panelX = $state(0);
	let panelY = $state(0);

	function updatePosition() {
		if (!triggerEl) return;
		const rect = triggerEl.getBoundingClientRect();
		panelX = rect.left;
		panelY = rect.bottom + 4;
	}

	// Parse on mount
	$effect(() => {
		parseRrule(rrule);
	});

	function parseRrule(s: string) {
		if (!s) return;
		if (s.includes('COUNT=1')) {
			frequency = 'ONCE';
			const match = s.match(/DTSTART:(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})/);
			if (match) {
				onceDate = `${match[1]}-${match[2]}-${match[3]}`;
				onceTime = `${match[4]}:${match[5]}`;
			}
			return;
		}
		const parts: Record<string, string> = {};
		s.replace('RRULE:', '')
			.split(';')
			.forEach((p) => {
				const [k, v] = p.split('=');
				if (k && v) parts[k] = v;
			});
		const freq = parts.FREQ || 'DAILY';
		if (!['HOURLY', 'DAILY', 'WEEKLY', 'MONTHLY'].includes(freq)) {
			frequency = 'CUSTOM';
			customRrule = s;
			return;
		}
		frequency = freq as Frequency;
		hour = parseInt(parts.BYHOUR || '9');
		minute = parseInt(parts.BYMINUTE || '0');
		selectedDays = parts.BYDAY ? parts.BYDAY.split(',') : [];
		monthDay = parseInt(parts.BYMONTHDAY || '1');
	}

	function buildRrule(): string {
		if (frequency === 'CUSTOM') return customRrule;
		if (frequency === 'ONCE') {
			const dt = onceDate.replace(/-/g, '') + 'T' + onceTime.replace(/:/g, '') + '00';
			return `DTSTART:${dt}\nRRULE:FREQ=DAILY;COUNT=1`;
		}
		let parts = [`FREQ=${frequency}`];
		if (frequency === 'WEEKLY' && selectedDays.length) {
			parts.push(`BYDAY=${selectedDays.join(',')}`);
		}
		if (frequency === 'MONTHLY') {
			parts.push(`BYMONTHDAY=${monthDay}`);
		}
		if (['DAILY', 'WEEKLY', 'MONTHLY'].includes(frequency)) {
			parts.push(`BYHOUR=${hour}`);
		}
		parts.push(`BYMINUTE=${minute}`);
		return `RRULE:${parts.join(';')}`;
	}

	function emitChange() {
		rrule = buildRrule();
		onchange?.(rrule);
	}

	function toggleDay(day: string) {
		if (selectedDays.includes(day)) {
			selectedDays = selectedDays.filter((d) => d !== day);
		} else {
			selectedDays = [...selectedDays, day];
		}
		emitChange();
	}

	let scheduleLabel = $derived(
		$t(FREQUENCIES.find((item) => item.key === frequency)?.labelKey ?? 'automations.schedule')
	);
</script>

<div class="schedule-dropdown">
	<button
		bind:this={triggerEl}
		type="button"
		class="schedule-trigger"
		onclick={() => {
			updatePosition();
			showDropdown = !showDropdown;
		}}
	>
		<svg
			xmlns="http://www.w3.org/2000/svg"
			fill="none"
			viewBox="0 0 24 24"
			stroke-width="1.5"
			stroke="currentColor"
			class="w-3.5 h-3.5"
		>
			<path
				stroke-linecap="round"
				stroke-linejoin="round"
				d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z"
			/>
		</svg>
		<span>{scheduleLabel}</span>
		<svg
			xmlns="http://www.w3.org/2000/svg"
			fill="none"
			viewBox="0 0 24 24"
			stroke-width="2"
			stroke="currentColor"
			class="w-2.5 h-2.5"
		>
			<path stroke-linecap="round" stroke-linejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
		</svg>
	</button>
</div>

{#if showDropdown}
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div class="fixed inset-0 z-[200]" onmousedown={() => (showDropdown = false)}></div>
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="schedule-panel"
		style="left:{panelX}px; top:{panelY}px;"
		onmousedown={(e) => e.stopPropagation()}
	>
		<div class="px-2 text-xs text-gray-500 pt-1">{$t('automations.schedule')}</div>

		<div class="px-1.5 py-0.5">
			<select
				class="w-full bg-transparent rounded-xl text-xs py-1.5 px-1.5 outline-none"
				bind:value={frequency}
				onchange={emitChange}
			>
				{#each FREQUENCIES as f}
					<option value={f.key}>{$t(f.labelKey)}</option>
				{/each}
			</select>
		</div>

		{#if frequency === 'CUSTOM'}
			<div class="px-2 pb-2">
				<input
					type="text"
					bind:value={customRrule}
					placeholder="RRULE:FREQ=DAILY;BYHOUR=9;BYMINUTE=0"
					class="w-full bg-transparent outline-none text-xs placeholder:text-gray-400 dark:placeholder:text-gray-600"
					oninput={emitChange}
				/>
			</div>
		{:else if frequency === 'ONCE'}
			<div class="flex gap-2 flex-wrap items-center px-3 pb-2 text-xs">
				<input
					type="date"
					bind:value={onceDate}
					min={new Date().toISOString().split('T')[0]}
					class="bg-transparent outline-none text-xs"
					oninput={emitChange}
				/>
				<input
					type="time"
					bind:value={onceTime}
					class="bg-transparent outline-none text-xs"
					oninput={emitChange}
				/>
			</div>
		{:else if frequency !== 'HOURLY'}
			<div class="flex gap-2 flex-wrap items-center px-3 pb-2 text-xs">
				<div class="flex items-center gap-1.5">
					<span class="text-xs text-gray-500 mr-0.5">{$t('automations.time')}</span>
					<input
						type="time"
						value={`${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`}
						oninput={(e) => {
							const [h, m] = e.currentTarget.value.split(':').map(Number);
							hour = h;
							minute = m;
							emitChange();
						}}
						class="bg-transparent text-center outline-none text-xs"
					/>
				</div>

				{#if frequency === 'MONTHLY'}
					<div class="flex items-center gap-1.5">
						<span class="text-xs text-gray-500">{$t('automations.day')}</span>
						<input
							type="number"
							bind:value={monthDay}
							min={1}
							max={31}
							class="w-8 bg-transparent text-center outline-none text-xs"
							oninput={emitChange}
						/>
					</div>
				{/if}
			</div>

			{#if frequency === 'WEEKLY'}
				<div class="flex gap-1 px-2 pb-2">
					{#each DAYS as d}
						<button
							type="button"
							class="flex-1 py-1 text-xs rounded-xl transition {selectedDays.includes(d.key)
								? 'bg-gray-100 dark:bg-gray-800 text-black dark:text-gray-100'
								: 'text-gray-400 dark:text-gray-500 hover:text-gray-700 dark:hover:text-gray-200'}"
							onclick={() => toggleDay(d.key)}
						>
							{$t(d.labelKey)}
						</button>
					{/each}
				</div>
			{/if}
		{/if}
	</div>
{/if}

<style>
	@reference "../../../app.css";

	.schedule-dropdown {
		position: relative;
	}

	.schedule-trigger {
		display: flex;
		align-items: center;
		gap: 0.375rem;
		padding: 0.25rem 0.625rem;
		border-radius: 1rem;
		font-size: 0.75rem;
		color: var(--app-fg-muted);
		transition: background 0.1s;
	}

	.schedule-trigger:hover {
		background: var(--app-hover);
	}

	.schedule-panel {
		position: fixed;
		z-index: 201;
		width: 12rem;
		padding: 0.25rem;
		border-radius: 1rem;
		background: var(--app-bg);
		border: 1px solid var(--app-border);
		box-shadow:
			0 0.25rem 0.375rem -0.0625rem color-mix(in oklab, var(--app-fg) 10%, transparent),
			0 0.125rem 0.25rem -0.125rem color-mix(in oklab, var(--app-fg) 10%, transparent);
	}
</style>
