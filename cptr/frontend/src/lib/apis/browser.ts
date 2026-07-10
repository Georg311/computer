import { fetchHandler, fetchJSON } from '$lib/apis';

export interface BrowserSession {
	session_id: string;
	url: string;
	title: string;
}

export const createBrowserSession = () =>
	fetchJSON<BrowserSession>('/api/browser/sessions', { method: 'POST' });

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

export const browserFrameUrl = (sessionId: string, rawUrl: string) => {
	const normalized = /^https?:\/\//i.test(rawUrl) ? rawUrl : `https://${rawUrl}`;
	const url = new URL(normalized);
	return `/api/browser/frame/${sessionId}?url=${encodeURIComponent(url.href)}`;
};

export const browserBlankUrl = (sessionId: string) => `/api/browser/sessions/${sessionId}/blank`;
