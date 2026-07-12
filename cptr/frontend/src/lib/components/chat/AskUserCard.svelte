<script lang="ts">
	interface Props {
		item: any;
		pairedOutput: any;
		chatId: string | null;
		messageId: string;
		onanswer: (
			messageId: string,
			callId: string,
			answers: Record<string, string>,
			timedOut: boolean
		) => void;
	}

	let { item, pairedOutput, chatId, messageId, onanswer }: Props = $props();
	let selections = $state<Record<string, string>>({});
	let otherAnswers = $state<Record<string, string>>({});
	let now = $state(Date.now());
	let submitting = $state(false);
	const request = $derived(item.arguments || {});
	const questions = $derived(Array.isArray(request.questions) ? request.questions : []);
	const pending = $derived(item.status === 'pending');
	const secondsRemaining = $derived(Math.max(0, Math.ceil((Number(item.expires_at) - now) / 1000)));
	const canSubmit = $derived(
		questions.length > 0 &&
			questions.every((question: any) => {
				const choice = selections[question.id];
				return choice && (choice !== '__other__' || otherAnswers[question.id]?.trim());
			})
	);
	const resolved = $derived.by(() => {
		try {
			return JSON.parse(pairedOutput?.output || '{}');
		} catch {
			return {};
		}
	});

	$effect(() => {
		if (!pending) return;
		now = Date.now();
		const timer = window.setInterval(() => (now = Date.now()), 1000);
		return () => window.clearInterval(timer);
	});

	function timeLabel(seconds: number) {
		return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
	}

	function submit(timedOut = false) {
		if (!chatId || (!canSubmit && !timedOut)) return;
		const answers: Record<string, string> = {};
		for (const question of questions) {
			const choice = selections[question.id];
			answers[question.id] = timedOut
				? question.options[0].label
				: choice === '__other__'
					? otherAnswers[question.id].trim()
					: choice;
		}
		submitting = true;
		onanswer(messageId, item.call_id, answers, timedOut);
	}
</script>

<section
	class="my-2 overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-white/10 dark:bg-white/[0.03]"
>
	<div
		class="flex items-center justify-between gap-3 border-b border-gray-100 px-3 py-2 dark:border-white/8"
	>
		<div class="text-xs font-medium text-gray-800 dark:text-gray-100">Planning question</div>
		{#if pending}
			<div class="text-[0.6875rem] text-gray-500 dark:text-gray-400">
				Continuing with recommendations in {timeLabel(secondsRemaining)}
			</div>
		{:else if item.timed_out || resolved.timed_out}
			<div class="text-[0.6875rem] text-gray-500 dark:text-gray-400">Used recommendations</div>
		{/if}
	</div>

	<div class="space-y-4 px-3 py-3">
		{#each questions as question}
			<div class="space-y-2">
				<div>
					<div class="text-xs font-medium text-gray-800 dark:text-gray-100">{question.header}</div>
					<div class="mt-0.5 text-xs text-gray-600 dark:text-gray-300">{question.question}</div>
				</div>
				{#if pending}
					<div class="space-y-1.5">
						{#each question.options || [] as option, optionIndex}
							<label
								class="flex cursor-pointer gap-2 rounded-lg border border-gray-200 px-2.5 py-2 text-xs dark:border-white/10"
							>
								<input
									type="radio"
									name={question.id}
									value={option.label}
									checked={selections[question.id] === option.label}
									onchange={() => (selections = { ...selections, [question.id]: option.label })}
								/>
								<span class="min-w-0">
									<span class="block text-gray-800 dark:text-gray-100">{option.label}</span>
									<span class="block text-gray-500 dark:text-gray-400">{option.description}</span>
									{#if optionIndex === 0}<span class="text-gray-500 dark:text-gray-400"
											>Recommended</span
										>{/if}
								</span>
							</label>
						{/each}
						<label
							class="flex cursor-pointer gap-2 rounded-lg border border-gray-200 px-2.5 py-2 text-xs dark:border-white/10"
						>
							<input
								type="radio"
								name={question.id}
								value="__other__"
								checked={selections[question.id] === '__other__'}
								onchange={() => (selections = { ...selections, [question.id]: '__other__' })}
							/>
							<span class="text-gray-800 dark:text-gray-100">Other</span>
						</label>
						{#if selections[question.id] === '__other__'}
							<input
								class="w-full rounded-lg border border-gray-200 bg-transparent px-2.5 py-2 text-xs outline-none dark:border-white/10"
								placeholder="Type your answer"
								value={otherAnswers[question.id] || ''}
								oninput={(event) =>
									(otherAnswers = { ...otherAnswers, [question.id]: event.currentTarget.value })}
							/>
						{/if}
					</div>
				{:else}
					<div class="text-xs text-gray-600 dark:text-gray-300">
						{resolved.answers?.[question.id]?.answers?.join(', ') || 'No answer recorded'}
					</div>
				{/if}
			</div>
		{/each}

		{#if pending}
			<button
				type="button"
				class="rounded-lg bg-gray-900 px-3 py-1.5 text-xs font-medium text-white disabled:cursor-not-allowed disabled:opacity-40 dark:bg-white dark:text-black"
				disabled={!canSubmit || submitting}
				onclick={() => submit()}
			>
				Submit answers
			</button>
		{/if}
	</div>
</section>
