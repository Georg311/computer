/**
 * Audio state: voice memos feature flag, transcription toggle, recording quality, and modal visibility.
 */
import { writable } from 'svelte/store';
import { fetchJSON } from '$lib/apis';

export type RecordingQuality = 'high' | 'medium' | 'low';

export const QUALITY_BITRATES: Record<RecordingQuality, number> = {
	high: 128000,
	medium: 64000,
	low: 32000
};

export const voiceMemosEnabled = writable<boolean>(false);
export const transcribeEnabled = writable<boolean>(true);
export const sttConfigured = writable<boolean>(false);
export const recordingQuality = writable<RecordingQuality>('high');
export const showVoiceMemo = writable<boolean>(false);
export const ttsEnabled = writable<boolean>(false);
export const ttsConfigured = writable<boolean>(false);
export const ttsVoice = writable<string>('alloy');
export const ttsFormat = writable<string>('mp3');
export const ttsPlaybackSpeed = writable<number>(1);
export const ttsAutoStreamEnabled = writable<boolean>(false);
export const voiceModeSttMode = writable<'browser' | 'provider'>('browser');
export const ttsPlaybackEnabled = writable<boolean>(
	typeof localStorage !== 'undefined'
		? localStorage.getItem('ttsPlaybackEnabled') === 'true'
		: false
);

const SILENT_WAV =
	'data:audio/wav;base64,UklGRigAAABXQVZFZm10IBAAAAABAAEAESsAACJWAAACABAAZGF0YQQAAAAAAA==';

let ttsAudioElement: HTMLAudioElement | null = null;
let ttsAudioContext: AudioContext | null = null;
let ttsAudioUnlocked = false;
let ttsAudioUseToken = 0;
let currentTtsPlaybackSpeed = 1;

ttsPlaybackEnabled.subscribe((v) => {
	if (typeof localStorage !== 'undefined') localStorage.setItem('ttsPlaybackEnabled', String(v));
});

ttsPlaybackSpeed.subscribe((v) => {
	currentTtsPlaybackSpeed = Number.isFinite(v) ? Math.min(Math.max(v, 0.5), 2) : 1;
	if (ttsAudioElement) ttsAudioElement.playbackRate = currentTtsPlaybackSpeed;
});

export function getTtsAudioElement(): HTMLAudioElement | null {
	if (typeof Audio === 'undefined') return null;
	if (!ttsAudioElement) {
		ttsAudioElement = new Audio();
		ttsAudioElement.preload = 'auto';
		(ttsAudioElement as HTMLAudioElement & { playsInline?: boolean }).playsInline = true;
		ttsAudioElement.playbackRate = currentTtsPlaybackSpeed;
	}
	return ttsAudioElement;
}

export function setTtsAudioPlaybackSource(src: string, title?: string): HTMLAudioElement | null {
	const audio = getTtsAudioElement();
	if (!audio) return null;
	ttsAudioUseToken += 1;
	audio.pause();
	audio.volume = 1;
	audio.muted = false;
	audio.playbackRate = currentTtsPlaybackSpeed;
	audio.src = src;

	// Shows playback controls on lock screen (Android) and
	// Control Center (iOS) while TTS is playing.
	if ('mediaSession' in navigator) {
		navigator.mediaSession.metadata = new MediaMetadata({
			title: title || 'Computer',
			artist: 'Computer',
			artwork: [
				{ src: '/icon-192.png', sizes: '192x192', type: 'image/png' },
				{ src: '/icon-512.png', sizes: '512x512', type: 'image/png' }
			]
		});
		navigator.mediaSession.setActionHandler('play', () => {
			audio.play().catch(() => {});
		});
		navigator.mediaSession.setActionHandler('pause', () => {
			audio.pause();
		});
		navigator.mediaSession.setActionHandler('stop', () => {
			audio.pause();
			audio.currentTime = 0;
			clearMediaSession();
		});

		// Clear media session when playback ends naturally
		const currentToken = ttsAudioUseToken;
		audio.addEventListener('ended', function onEnd() {
			audio.removeEventListener('ended', onEnd);
			if (ttsAudioUseToken === currentToken) clearMediaSession();
		});
	}

	return audio;
}

/** Clear media session metadata and handlers. */
export function clearMediaSession() {
	if ('mediaSession' in navigator) {
		navigator.mediaSession.metadata = null;
		navigator.mediaSession.setActionHandler('play', null);
		navigator.mediaSession.setActionHandler('pause', null);
		navigator.mediaSession.setActionHandler('stop', null);
	}
}

export async function unlockTtsAudioPlayback() {
	if (typeof window === 'undefined') return;

	const unlocks: Promise<unknown>[] = [];
	const AudioContextCtor =
		window.AudioContext ||
		(window as Window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
	try {
		if (AudioContextCtor) {
			ttsAudioContext ??= new AudioContextCtor();
			const buffer = ttsAudioContext.createBuffer(1, 1, 22050);
			const source = ttsAudioContext.createBufferSource();
			source.buffer = buffer;
			source.connect(ttsAudioContext.destination);
			source.start(0);
			if (ttsAudioContext.state !== 'running') unlocks.push(ttsAudioContext.resume());
		}
	} catch {}

	const audio = getTtsAudioElement();
	if (audio && !ttsAudioUnlocked) {
		try {
			const unlockToken = ++ttsAudioUseToken;
			audio.src = SILENT_WAV;
			audio.volume = 0;
			audio.playbackRate = 1;
			const started = audio.play();
			unlocks.push(
				Promise.resolve(started)
					.then(() => {
						ttsAudioUnlocked = true;
					})
					.finally(() => {
						if (unlockToken !== ttsAudioUseToken) return;
						audio.pause();
						audio.currentTime = 0;
						audio.removeAttribute('src');
						audio.load();
						audio.volume = 1;
						audio.playbackRate = currentTtsPlaybackSpeed;
					})
			);
		} catch {}
	}

	await Promise.allSettled(unlocks);
}

export async function refreshAudioState() {
	try {
		const data = await fetchJSON<{
			voice_memos_enabled: boolean;
			transcribe_enabled: boolean;
			stt_configured: boolean;
			recording_quality: string;
			tts_enabled: boolean;
			tts_configured: boolean;
			tts_voice: string;
			tts_format: string;
			tts_playback_speed?: number;
			tts_auto_stream_enabled?: boolean;
			voice_mode_stt_mode?: string;
		}>('/api/audio/state');
		voiceMemosEnabled.set(data.voice_memos_enabled === true);
		transcribeEnabled.set(data.transcribe_enabled !== false);
		sttConfigured.set(data.stt_configured === true);
		const q = data.recording_quality;
		if (q === 'medium' || q === 'low') recordingQuality.set(q);
		else recordingQuality.set('high');
		ttsEnabled.set(data.tts_enabled === true);
		ttsConfigured.set(data.tts_configured === true);
		ttsVoice.set(data.tts_voice || 'alloy');
		ttsFormat.set(data.tts_format || 'mp3');
		const speed = Number(data.tts_playback_speed);
		ttsPlaybackSpeed.set(Number.isFinite(speed) ? Math.min(Math.max(speed, 0.5), 2) : 1);
		ttsAutoStreamEnabled.set(data.tts_auto_stream_enabled === true);
		voiceModeSttMode.set(data.voice_mode_stt_mode === 'provider' ? 'provider' : 'browser');
	} catch {
		voiceMemosEnabled.set(false);
		sttConfigured.set(false);
		ttsEnabled.set(false);
		ttsConfigured.set(false);
		ttsPlaybackSpeed.set(1);
		ttsAutoStreamEnabled.set(false);
		voiceModeSttMode.set('browser');
	}
}
