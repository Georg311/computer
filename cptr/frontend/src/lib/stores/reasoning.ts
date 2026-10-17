import { getAdminConfig } from '$lib/apis/admin';

let _showReasoningTraces: boolean | undefined = undefined;

export const showReasoningTraces = {
	subscribe(run) {
		if (_showReasoningTraces !== undefined) {
			run(_showReasoningTraces);
		}
		return () => {};
	},
	get() {
		return _showReasoningTraces;
	},
	async init() {
		if (_showReasoningTraces !== undefined) return;
		try {
			const config = await getAdminConfig();
			const val = config['chat.reasoning_traces.enabled'];
			_showReasoningTraces = val !== false && val !== 'false';
		} catch {
			_showReasoningTraces = true;
		}
	}
};
