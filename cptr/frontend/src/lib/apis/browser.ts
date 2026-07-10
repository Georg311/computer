import { fetchHandler, fetchJSON } from '$lib/apis';

export interface BrowserSession {
	session_id: string;
	url: string;
	title: string;
	mode: 'proxy' | 'chrome';
	status: string;
}

export interface BrowserAvailability {
	proxy: { available: true };
	chrome: {
		available: boolean;
		browser_name: string | null;
		experimental: true;
		reason: string | null;
	};
}

let availabilityPromise: Promise<BrowserAvailability> | undefined;
export const getBrowserAvailability = () =>
	(availabilityPromise ??= fetchJSON<BrowserAvailability>('/api/browser/availability'));

export const createBrowserSession = (url?: string) =>
	fetchJSON<BrowserSession>('/api/browser/sessions', {
		method: 'POST',
		headers: { 'content-type': 'application/json' },
		body: JSON.stringify({ url })
	});

export const listBrowserSessions = async () => {
	const data = await fetchJSON<{ session_ids: string[] }>('/api/browser/sessions');
	return data.session_ids;
};

export const deleteBrowserSession = (sessionId: string) =>
	fetchHandler(`/api/browser/sessions/${sessionId}`, { method: 'DELETE' }).catch(() => {});

export const getBrowserSession = (sessionId: string) =>
	fetchJSON<BrowserSession>(`/api/browser/sessions/${sessionId}`);

export const updateBrowserSession = (sessionId: string, url: string, title: string) =>
	fetchJSON<BrowserSession>(`/api/browser/sessions/${sessionId}`, {
		method: 'PATCH',
		headers: { 'content-type': 'application/json' },
		body: JSON.stringify({ url, title })
	});

export const setBrowserMode = (sessionId: string, mode: 'proxy' | 'chrome', url: string) =>
	fetchJSON<BrowserSession>(`/api/browser/sessions/${sessionId}`, {
		method: 'PATCH',
		headers: { 'content-type': 'application/json' },
		body: JSON.stringify({ mode, url })
	});

export const browserFrameUrl = (sessionId: string, rawUrl: string) => {
	const normalized = /^https?:\/\//i.test(rawUrl) ? rawUrl : `https://${rawUrl}`;
	const url = new URL(normalized);
	return `/api/browser/frame/${sessionId}/${url.protocol.slice(0, -1)}/${encodeURIComponent(url.host)}${url.pathname}${url.search}${url.hash}`;
};

export const browserBlankUrl = (sessionId: string) => `/api/browser/sessions/${sessionId}/blank`;
