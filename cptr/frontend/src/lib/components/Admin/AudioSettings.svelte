<script lang="ts">
	import { toast } from 'svelte-sonner';
	import ToggleSwitch from '../common/ToggleSwitch.svelte';
	import Spinner from '../common/Spinner.svelte';
	import { onMount } from 'svelte';
	import { getAdminConfig, updateConfig } from '$lib/apis/admin';
	import { t } from '$lib/i18n';
	import { refreshAudioState } from '$lib/stores/audio';

	let loading = $state(true);
	let saving = $state(false);

	// Config state
	let voiceMemosEnabled = $state(false);
	let transcribeEnabled = $state(true);
	let quality = $state<'high' | 'medium' | 'low'>('high');
	let sttBaseUrl = $state('https://api.openai.com/v1');
	let sttApiKey = $state('');
	let sttModel = $state('whisper-1');
	let hasExistingKey = $state(false);
	let ttsBaseUrl = $state('https://api.openai.com/v1');
	let ttsEnabled = $state(false);
	let ttsApiKey = $state('');
	let ttsModel = $state('tts-1');
	let ttsVoice = $state('alloy');
	let ttsFormat = $state('mp3');
	let ttsPlaybackSpeed = $state(1);
	let ttsAutoStreamEnabled = $state(false);
	let hasExistingTtsKey = $state(false);
	let voiceModeSystemPrompt = $state('');
	let voiceModeSttMode = $state<'browser' | 'provider'>('browser');
	const VOICE_MODE_SYSTEM_PROMPT_PLACEHOLDER =
		'You are in voice mode. Keep responses brief, conversational, and easy to hear aloud. Prefer one or two short paragraphs. Ask at most one focused follow-up question when needed. Avoid long lists, code blocks, tables, and verbose explanations unless the user explicitly asks.';

	onMount(async () => {
		try {
			const config = await getAdminConfig();
			voiceMemosEnabled = config['audio.voice_memos_enabled'] === true;
			transcribeEnabled = config['audio.transcribe_enabled'] !== false;
			const q = config['audio.recording_quality'];
			if (q === 'medium' || q === 'low') quality = q;
			else quality = 'high';
			sttBaseUrl = (config['audio.stt_base_url'] as string) || 'https://api.openai.com/v1';
			sttModel = (config['audio.stt_model'] as string) || 'whisper-1';
			hasExistingKey = !!config['audio.stt_api_key'];
			ttsBaseUrl = (config['audio.tts_base_url'] as string) || 'https://api.openai.com/v1';
			ttsEnabled = config['audio.tts_enabled'] === true;
			ttsModel = (config['audio.tts_model'] as string) || 'tts-1';
			ttsVoice = (config['audio.tts_voice'] as string) || 'alloy';
			ttsFormat = (config['audio.tts_format'] as string) || 'mp3';
			const speed = Number(config['audio.tts_playback_speed']);
			ttsPlaybackSpeed = Number.isFinite(speed) ? Math.min(Math.max(speed, 0.5), 2) : 1;
			ttsAutoStreamEnabled = config['audio.tts_auto_stream_enabled'] === true;
			hasExistingTtsKey = !!config['audio.tts_api_key'];
			voiceModeSystemPrompt = (config['audio.voice_mode_system_prompt'] as string) || '';
			voiceModeSttMode =
				config['audio.voice_mode_stt_mode'] === 'provider' ? 'provider' : 'browser';
		} catch {}
		loading = false;
	});

	async function save() {
		saving = true;
		try {
			const cfg: Record<string, unknown> = {
				'audio.voice_memos_enabled': voiceMemosEnabled,
				'audio.transcribe_enabled': transcribeEnabled,
				'audio.recording_quality': quality,
				'audio.stt_base_url': sttBaseUrl,
				'audio.stt_model': sttModel,
				'audio.tts_enabled': ttsEnabled,
				'audio.tts_base_url': ttsBaseUrl,
				'audio.tts_model': ttsModel,
				'audio.tts_voice': ttsVoice,
				'audio.tts_format': ttsFormat,
				'audio.tts_playback_speed': ttsPlaybackSpeed,
				'audio.tts_auto_stream_enabled': ttsAutoStreamEnabled,
				'audio.voice_mode_system_prompt': voiceModeSystemPrompt,
				'audio.voice_mode_stt_mode': voiceModeSttMode
			};
			if (sttApiKey) {
				cfg['audio.stt_api_key'] = sttApiKey;
			}
			if (ttsApiKey) {
				cfg['audio.tts_api_key'] = ttsApiKey;
			}
			await updateConfig(cfg);
			if (sttApiKey) hasExistingKey = true;
			if (ttsApiKey) hasExistingTtsKey = true;
			toast.success($t('settings.saved'));
			refreshAudioState();
		} catch {
			toast.error($t('admin.audio.saveFailed'));
		} finally {
			saving = false;
		}
	}
</script>

<div class="flex flex-col h-full">
	{#if loading}
		<div class="flex justify-center py-8"><Spinner size={16} /></div>
	{:else}
		<div class="flex-1 min-h-0 overflow-y-auto">
			<h2 class="text-sm font-medium text-gray-900 dark:text-white mb-4">
				{$t('admin.audio.title')}
			</h2>

			<!-- Voice Notes -->
			<h3 class="text-xs text-gray-400 dark:text-gray-600 mb-2">{$t('admin.audio.voiceMemos')}</h3>

			<div class="flex flex-col gap-2.5">
				<label class="flex items-center justify-between cursor-pointer">
					<span class="text-xs text-gray-600 dark:text-gray-400"
						>{$t('admin.audio.enableVoiceMemos')}</span
					>
					<ToggleSwitch
						value={voiceMemosEnabled}
						onchange={(v) => {
							voiceMemosEnabled = v;
						}}
					/>
				</label>
				<p class="text-[0.6875rem] text-gray-400 dark:text-gray-600 -mt-1">
					{$t('admin.audio.voiceMemosHint')}
				</p>

				<label class="flex items-center justify-between cursor-pointer">
					<span class="text-xs text-gray-600 dark:text-gray-400"
						>{$t('admin.audio.autoTranscribe')}</span
					>
					<ToggleSwitch
						value={transcribeEnabled}
						onchange={(v) => {
							transcribeEnabled = v;
						}}
					/>
				</label>
				<p class="text-[0.6875rem] text-gray-400 dark:text-gray-600 -mt-1">
					{transcribeEnabled
						? $t('admin.audio.transcribeOnHint')
						: $t('admin.audio.transcribeOffHint')}
				</p>

				<div class="flex items-center justify-between">
					<span class="text-xs text-gray-600 dark:text-gray-400"
						>{$t('admin.audio.recordingQuality')}</span
					>
					<select
						bind:value={quality}
						class="bg-transparent text-xs text-gray-600 dark:text-gray-400 outline-none cursor-pointer"
					>
						<option value="high">{$t('admin.audio.qualityHigh')}</option>
						<option value="medium">{$t('admin.audio.qualityMedium')}</option>
						<option value="low">{$t('admin.audio.qualityLow')}</option>
					</select>
				</div>
				<p class="text-[0.6875rem] text-gray-400 dark:text-gray-600 -mt-1">
					{quality === 'high'
						? $t('admin.audio.qualityHintHigh')
						: quality === 'medium'
							? $t('admin.audio.qualityHintMedium')
							: $t('admin.audio.qualityHintLow')}
				</p>
			</div>

			<!-- Speech-to-Text -->
			<h3 class="text-xs text-gray-400 dark:text-gray-600 mb-2 mt-5">{$t('admin.audio.stt')}</h3>

			<div class="flex flex-col gap-2.5">
				<div>
					<label class="text-xs text-gray-600 dark:text-gray-400" for="stt-base-url"
						>{$t('connections.baseUrl')}</label
					>
					<input
						id="stt-base-url"
						type="text"
						bind:value={sttBaseUrl}
						placeholder="https://api.openai.com/v1"
						class="w-full mt-1 h-7 px-2 rounded-lg text-xs bg-gray-100 dark:bg-white/6 text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-white/8 outline-none focus:border-blue-400 dark:focus:border-blue-500 transition-colors"
					/>
				</div>
				<div>
					<label class="text-xs text-gray-600 dark:text-gray-400" for="stt-api-key"
						>{$t('connections.apiKey')}</label
					>
					<input
						id="stt-api-key"
						type="password"
						bind:value={sttApiKey}
						placeholder={hasExistingKey ? '••••••••' : 'sk-...'}
						class="w-full mt-1 h-7 px-2 rounded-lg text-xs bg-gray-100 dark:bg-white/6 text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-white/8 outline-none focus:border-blue-400 dark:focus:border-blue-500 transition-colors"
					/>
				</div>
				<div>
					<label class="text-xs text-gray-600 dark:text-gray-400" for="stt-model"
						>{$t('automations.model')}</label
					>
					<input
						id="stt-model"
						type="text"
						bind:value={sttModel}
						placeholder="whisper-1"
						class="w-full mt-1 h-7 px-2 rounded-lg text-xs bg-gray-100 dark:bg-white/6 text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-white/8 outline-none focus:border-blue-400 dark:focus:border-blue-500 transition-colors"
					/>
				</div>
				<p class="text-[0.6875rem] text-gray-400 dark:text-gray-600">
					{$t('admin.audio.sttHint')}
				</p>
			</div>

			<!-- Text-to-Speech -->
			<h3 class="text-xs text-gray-400 dark:text-gray-600 mb-2 mt-5">{$t('admin.audio.tts')}</h3>

			<div class="flex flex-col gap-2.5">
				<label class="flex items-center justify-between cursor-pointer">
					<span class="text-xs text-gray-600 dark:text-gray-400">{$t('admin.audio.enableTts')}</span
					>
					<ToggleSwitch
						value={ttsEnabled}
						onchange={(v) => {
							ttsEnabled = v;
						}}
					/>
				</label>
				<p class="text-[0.6875rem] text-gray-400 dark:text-gray-600 -mt-1">
					{$t('admin.audio.ttsEnabledHint')}
				</p>
				<label class="flex items-center justify-between cursor-pointer">
					<span class="text-xs text-gray-600 dark:text-gray-400"
						>{$t('admin.audio.ttsAutoStream')}</span
					>
					<ToggleSwitch
						value={ttsAutoStreamEnabled}
						onchange={(v) => {
							ttsAutoStreamEnabled = v;
						}}
					/>
				</label>
				<p class="text-[0.6875rem] text-gray-400 dark:text-gray-600 -mt-1">
					{$t('admin.audio.ttsAutoStreamHint')}
				</p>
				<div>
					<label class="text-xs text-gray-600 dark:text-gray-400" for="tts-base-url"
						>{$t('connections.baseUrl')}</label
					>
					<input
						id="tts-base-url"
						type="text"
						bind:value={ttsBaseUrl}
						placeholder="https://api.openai.com/v1"
						class="w-full mt-1 h-7 px-2 rounded-lg text-xs bg-gray-100 dark:bg-white/6 text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-white/8 outline-none focus:border-blue-400 dark:focus:border-blue-500 transition-colors"
					/>
				</div>
				<div>
					<label class="text-xs text-gray-600 dark:text-gray-400" for="tts-api-key"
						>{$t('connections.apiKey')}</label
					>
					<input
						id="tts-api-key"
						type="password"
						bind:value={ttsApiKey}
						placeholder={hasExistingTtsKey ? '••••••••' : $t('admin.audio.ttsKeyPlaceholder')}
						class="w-full mt-1 h-7 px-2 rounded-lg text-xs bg-gray-100 dark:bg-white/6 text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-white/8 outline-none focus:border-blue-400 dark:focus:border-blue-500 transition-colors"
					/>
				</div>
				<div>
					<label class="text-xs text-gray-600 dark:text-gray-400" for="tts-model"
						>{$t('automations.model')}</label
					>
					<input
						id="tts-model"
						type="text"
						bind:value={ttsModel}
						placeholder="tts-1"
						class="w-full mt-1 h-7 px-2 rounded-lg text-xs bg-gray-100 dark:bg-white/6 text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-white/8 outline-none focus:border-blue-400 dark:focus:border-blue-500 transition-colors"
					/>
				</div>
				<div>
					<label class="text-xs text-gray-600 dark:text-gray-400" for="tts-voice"
						>{$t('admin.audio.ttsVoice')}</label
					>
					<input
						id="tts-voice"
						type="text"
						bind:value={ttsVoice}
						placeholder="alloy"
						class="w-full mt-1 h-7 px-2 rounded-lg text-xs bg-gray-100 dark:bg-white/6 text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-white/8 outline-none focus:border-blue-400 dark:focus:border-blue-500 transition-colors"
					/>
				</div>
				<div class="flex items-center justify-between">
					<span class="text-xs text-gray-600 dark:text-gray-400">{$t('admin.audio.ttsFormat')}</span
					>
					<select
						bind:value={ttsFormat}
						class="bg-transparent text-xs text-gray-600 dark:text-gray-400 outline-none cursor-pointer"
					>
						<option value="mp3">MP3</option>
						<option value="opus">Opus</option>
						<option value="aac">AAC</option>
						<option value="flac">FLAC</option>
						<option value="wav">WAV</option>
						<option value="pcm">PCM</option>
					</select>
				</div>
				<div class="flex items-center justify-between gap-3">
					<label class="text-xs text-gray-600 dark:text-gray-400" for="tts-playback-speed">
						{$t('admin.audio.ttsPlaybackSpeed')}
					</label>
					<div class="flex items-center gap-2">
						<input
							id="tts-playback-speed"
							type="range"
							min="0.5"
							max="2"
							step="0.05"
							bind:value={ttsPlaybackSpeed}
							class="w-28 accent-gray-700 dark:accent-gray-300"
						/>
						<span class="w-9 text-right text-xs text-gray-500 dark:text-gray-400"
							>{ttsPlaybackSpeed.toFixed(2)}x</span
						>
					</div>
				</div>
				<p class="text-[0.6875rem] text-gray-400 dark:text-gray-600">
					{$t('admin.audio.ttsHint')}
				</p>
			</div>

			<!-- Voice Mode -->
			<h3 class="text-xs text-gray-400 dark:text-gray-600 mb-2 mt-5">
				{$t('admin.audio.voiceMode')}
			</h3>

			<div class="flex flex-col gap-2.5">
				<div class="flex items-center justify-between">
					<span class="text-xs text-gray-600 dark:text-gray-400"
						>{$t('admin.audio.voiceModeSttMode')}</span
					>
					<select
						bind:value={voiceModeSttMode}
						class="bg-transparent text-xs text-gray-600 dark:text-gray-400 outline-none cursor-pointer"
					>
						<option value="browser">{$t('admin.audio.voiceModeSttBrowser')}</option>
						<option value="provider">{$t('admin.audio.voiceModeSttProvider')}</option>
					</select>
				</div>
				<p class="text-[0.6875rem] text-gray-400 dark:text-gray-600 -mt-1">
					{voiceModeSttMode === 'browser'
						? $t('admin.audio.voiceModeBrowserSttHint')
						: $t('admin.audio.voiceModeProviderSttHint')}
				</p>
				<div>
					<label class="text-xs text-gray-600 dark:text-gray-400" for="voice-mode-system-prompt">
						{$t('admin.audio.voiceModeSystemPrompt')}
					</label>
					<textarea
						id="voice-mode-system-prompt"
						bind:value={voiceModeSystemPrompt}
						rows="5"
						placeholder={VOICE_MODE_SYSTEM_PROMPT_PLACEHOLDER}
						class="w-full mt-1 px-2 py-1.5 rounded-lg text-xs bg-gray-100 dark:bg-white/6 text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-white/8 outline-none focus:border-blue-400 dark:focus:border-blue-500 transition-colors resize-y min-h-24"
					></textarea>
				</div>
				<p class="text-[0.6875rem] text-gray-400 dark:text-gray-600">
					{$t('admin.audio.voiceModeSystemPromptHint')}
				</p>
			</div>
		</div>

		<!-- Save -->
		<div class="shrink-0 pt-3 flex justify-end">
			<button
				class="text-[0.8125rem] text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors duration-100 disabled:opacity-50"
				onclick={() => save()}
				disabled={saving}
			>
				{#if saving}{$t('settings.saving')}{:else}{$t('settings.save')}{/if}
			</button>
		</div>
	{/if}
</div>
