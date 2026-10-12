<script lang="ts">
	import { t } from '$lib/i18n';
	interface Props {
		ontext: (text: string) => void;
	}
	let { ontext }: Props = $props();

	let recording = $state(false);
	let recognition: any = null;

	function toggle() {
		if (recording) {
			stop();
			return;
		}
		const SpeechRecognition =
			(window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
		if (!SpeechRecognition) {
			alert($t('chat.dictate.unsupported'));
			return;
		}
		recognition = new SpeechRecognition();
		recognition.continuous = true;
		recognition.interimResults = false;
		recognition.lang = navigator.language || 'en-US';

		recognition.onresult = (event: any) => {
			const last = event.results[event.results.length - 1];
			if (last.isFinal) {
				ontext(last[0].transcript);
			}
		};

		recognition.onerror = () => {
			recording = false;
			recognition = null;
		};

		recognition.onend = () => {
			recording = false;
			recognition = null;
		};

		recognition.start();
		recording = true;
	}

	function stop() {
		recognition?.stop();
		recording = false;
		recognition = null;
	}
</script>

<button
	type="button"
	class="flex items-center justify-center rounded-full p-1 transition-colors duration-100
		{recording
		? 'text-gray-400 dark:text-gray-500 bg-gray-50 dark:bg-white/5'
		: 'text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-400 hover:bg-gray-50 dark:hover:bg-white/5'}"
	onclick={toggle}
>
	<svg
		class="size-4"
		viewBox="0 0 24 24"
		fill="none"
		stroke="currentColor"
		stroke-width="1.75"
		stroke-linecap="round"
		stroke-linejoin="round"
	>
		<rect x="9" y="2" width="6" height="12" rx="3" />
		<path d="M5 10a7 7 0 0 0 14 0" />
		<line x1="12" y1="19" x2="12" y2="22" />
		<line x1="8" y1="22" x2="16" y2="22" />
	</svg>
</button>
