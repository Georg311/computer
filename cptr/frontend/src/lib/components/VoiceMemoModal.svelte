<script lang="ts">
	import { onMount } from 'svelte';
	import { get } from 'svelte/store';
	import { toast } from 'svelte-sonner';
	import Modal from './Modal.svelte';
	import Spinner from './common/Spinner.svelte';
	import { writeFile } from '$lib/apis/files';
	import { fetchJSON } from '$lib/apis';
	import { transcribeEnabled, recordingQuality, QUALITY_BITRATES } from '$lib/stores/audio';
	import { t } from '$lib/i18n';

	interface Props {
		workspace: string;
		directory: string;
		onclose: () => void;
	}

	let { workspace, directory, onclose }: Props = $props();

	type Phase = 'recording' | 'processing' | 'naming' | 'done';
	let phase = $state<Phase>('recording');
	let elapsed = $state(0);
	let transcript = $state('');
	let fileName = $state('');
	let audioBlob = $state<Blob | null>(null);

	let waveformBars = $state<number[]>(new Array(40).fill(2));

	let mediaRecorder: MediaRecorder | null = null;
	let audioContext: AudioContext | null = null;
	let analyser: AnalyserNode | null = null;
	let animFrame = 0;
	let timerInterval = 0;
	let chunks: Blob[] = [];
	let cancelled = false;
	let filenameInput: HTMLInputElement | undefined = $state();

	// ── IndexedDB ───────────────────────────────────────────────

	const IDB_NAME = 'cptr-voice-notes';
	const IDB_STORE = 'pending';

	function openIDB(): Promise<IDBDatabase> {
		return new Promise((resolve, reject) => {
			const req = indexedDB.open(IDB_NAME, 1);
			req.onupgradeneeded = () => req.result.createObjectStore(IDB_STORE, { keyPath: 'id' });
			req.onsuccess = () => resolve(req.result);
			req.onerror = () => reject(req.error);
		});
	}

	async function saveToIDB(id: string, blob: Blob) {
		const db = await openIDB();
		const tx = db.transaction(IDB_STORE, 'readwrite');
		tx.objectStore(IDB_STORE).put({ id, blob, directory, createdAt: Date.now() });
		return new Promise<void>((r, j) => {
			tx.oncomplete = () => r();
			tx.onerror = () => j(tx.error);
		});
	}

	async function clearFromIDB(id: string) {
		const db = await openIDB();
		db.transaction(IDB_STORE, 'readwrite').objectStore(IDB_STORE).delete(id);
	}

	// ── Helpers ──────────────────────────────────────────────────

	function generateId(): string {
		const d = new Date();
		const p = (n: number) => n.toString().padStart(2, '0');
		return `recording-${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}-${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`;
	}

	function fmt(s: number): string {
		return `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, '0')}`;
	}

	function mimeType(): string {
		for (const t of ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg'])
			if (MediaRecorder.isTypeSupported(t)) return t;
		return 'audio/webm';
	}

	function ext(blob: Blob): string {
		return blob.type.includes('mp4') ? 'mp4' : blob.type.includes('ogg') ? 'ogg' : 'webm';
	}

	// ── Recording ───────────────────────────────────────────────

	async function startRecording() {
		try {
			const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
			audioContext = new AudioContext();
			analyser = audioContext.createAnalyser();
			analyser.fftSize = 64;
			audioContext.createMediaStreamSource(stream).connect(analyser);

			const buf = new Uint8Array(analyser.frequencyBinCount);
			const tick = () => {
				if (!analyser) return;
				analyser.getByteFrequencyData(buf);
				waveformBars = Array.from({ length: 40 }, (_, i) =>
					Math.max(2, (buf[Math.floor((i / 40) * buf.length)] / 255) * 20)
				);
				animFrame = requestAnimationFrame(tick);
			};
			tick();

			chunks = [];
			mediaRecorder = new MediaRecorder(stream, {
				mimeType: mimeType(),
				audioBitsPerSecond: QUALITY_BITRATES[get(recordingQuality)]
			});
			mediaRecorder.ondataavailable = (e) => {
				if (e.data.size > 0) chunks.push(e.data);
			};
			mediaRecorder.onstop = () => {
				stream.getTracks().forEach((t) => t.stop());
				cancelAnimationFrame(animFrame);
				audioContext?.close();
				if (cancelled) return;
				audioBlob = new Blob(chunks, { type: mediaRecorder?.mimeType || 'audio/webm' });
				handleComplete();
			};
			mediaRecorder.start(250);
			elapsed = 0;
			timerInterval = window.setInterval(() => elapsed++, 1000);
		} catch {
			toast.error($t('voiceMemo.microphoneError'));
			onclose();
		}
	}

	function stop() {
		if (timerInterval) clearInterval(timerInterval);
		if (mediaRecorder?.state !== 'inactive') mediaRecorder?.stop();
	}

	function cancel() {
		cancelled = true;
		stop();
		onclose();
	}

	// ── Save-first flow ─────────────────────────────────────────

	async function handleComplete() {
		if (!audioBlob) return;
		const id = generateId();
		fileName = id;
		phase = 'processing';

		// 1. IndexedDB safety
		try {
			await saveToIDB(id, audioBlob);
		} catch {}

		// 2. Upload audio
		const audioName = `${id}.${ext(audioBlob)}`;
		const form = new FormData();
		form.append('directory', directory);
		form.append('file', new File([audioBlob], audioName, { type: audioBlob.type }));
		try {
			await fetchJSON('/api/workspace/files/upload', { method: 'POST', body: form });
			await clearFromIDB(id).catch(() => {});
		} catch {
			toast.error($t('voiceMemo.uploadFailed'));
		}

		// 3. Transcribe (if enabled)
		if (get(transcribeEnabled)) {
			try {
				const tf = new FormData();
				tf.append('file', new File([audioBlob], audioName, { type: audioBlob.type }));
				tf.append('workspace', workspace);
				const res = await fetchJSON<{ text: string }>('/api/audio/transcribe', {
					method: 'POST',
					body: tf
				});
				transcript = res.text || '';
			} catch (err: any) {
				transcript = '';
				const msg = err?.message || '';
				if (msg.includes('not configured')) {
					toast.error($t('voiceMemo.sttNotConfigured'));
				}
			}
		}

		phase = 'naming';
		await new Promise((r) => setTimeout(r, 50));
		filenameInput?.focus();
		filenameInput?.select();
	}

	async function save() {
		if (!fileName.trim()) return;
		const n = fileName.trim();
		const audioFile = `${n}.${ext(audioBlob!)}`;
		const mdPath = `${directory}/${n}.md`;
		const date = new Date().toLocaleDateString('en-US', {
			month: 'short',
			day: 'numeric',
			year: 'numeric',
			hour: 'numeric',
			minute: '2-digit'
		});

		let md = `# ${date}\n\n*${fmt(elapsed)}*\n\n`;
		if (transcript) md += `${transcript}\n\n`;
		md += `---\n[🔊 ${audioFile}](${audioFile})\n`;

		try {
			await writeFile(mdPath, md);
			phase = 'done';
			setTimeout(onclose, 500);
		} catch {
			toast.error($t('voiceMemo.writeFailed'));
		}
	}

	onMount(() => {
		startRecording();
		return () => {
			if (timerInterval) clearInterval(timerInterval);
			cancelAnimationFrame(animFrame);
			if (mediaRecorder?.state !== 'inactive') mediaRecorder?.stop();
			audioContext?.close().catch(() => {});
		};
	});
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<Modal onclose={phase === 'recording' ? cancel : onclose} class="w-full max-w-[16.25rem] mx-4">
	<div
		class="px-4 py-3.5"
		onkeydown={(e) => {
			if (phase === 'naming' && e.key === 'Enter') {
				e.preventDefault();
				save();
			}
		}}
	>
		{#if phase === 'recording'}
			<div class="flex items-center gap-2.5 mt-0.5">
				<div class="flex items-end gap-px h-4 flex-1">
					{#each waveformBars as h}
						<div
							class="flex-1 rounded-full bg-gray-300 dark:bg-gray-700 transition-all duration-75"
							style="height: {h}px"
						></div>
					{/each}
				</div>
				<span class="text-xs font-mono text-gray-400 dark:text-gray-600 tabular-nums shrink-0"
					>{fmt(elapsed)}</span
				>
			</div>

			<div class="flex items-center justify-end gap-3 mt-3">
				<button
					class="text-[0.8125rem] text-gray-400 dark:text-gray-600 hover:text-gray-600 dark:hover:text-gray-400 transition-colors"
					onclick={cancel}>{$t('common.cancel')}</button
				>
				<button
					class="text-[0.8125rem] text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors duration-100"
					onclick={stop}>{$t('voiceMemo.done')}</button
				>
			</div>
		{:else if phase === 'processing'}
			<div class="flex items-center gap-2">
				<Spinner size={12} />
				<span class="text-xs text-gray-400 dark:text-gray-600">{$t('voiceMemo.processing')}</span>
			</div>
		{:else if phase === 'naming'}
			{#if transcript}
				<p class="text-xs text-gray-400 dark:text-gray-600 line-clamp-2 mb-2">
					{transcript.slice(0, 140)}{transcript.length > 140 ? '…' : ''}
				</p>
			{/if}

			<label class="text-[0.625rem] text-gray-400 dark:text-gray-600"
				>{$t('voiceMemo.filename')}</label
			>
			<input
				bind:this={filenameInput}
				type="text"
				bind:value={fileName}
				placeholder={$t('voiceMemo.filenamePlaceholder')}
				autocomplete="off"
				spellcheck="false"
				class="block w-full bg-transparent text-[0.8125rem] text-gray-700 dark:text-gray-300 placeholder:text-gray-300 dark:placeholder:text-gray-700 outline-none py-0.5"
			/>
			<p class="text-[0.625rem] text-gray-300 dark:text-gray-700 mt-0.5">
				{directory.split('/').pop()}
			</p>

			<div class="flex justify-end mt-3">
				<button
					onclick={save}
					disabled={!fileName.trim()}
					class="text-[0.8125rem] text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors duration-100 disabled:opacity-30 disabled:pointer-events-none"
					>{$t('common.save')} →</button
				>
			</div>
		{:else if phase === 'done'}
			<p class="text-xs text-gray-400 dark:text-gray-600">{$t('voiceMemo.saved')}</p>
		{/if}
	</div>
</Modal>
