import { fetchJSON, jsonBody } from '$lib/apis';

export const CHAT_NOTIFICATION_EVENTS = {
	FINISHED: 'chat.finished',
	FAILED: 'chat.failed'
} as const;

export type ChatNotificationEvent =
	(typeof CHAT_NOTIFICATION_EVENTS)[keyof typeof CHAT_NOTIFICATION_EVENTS];
export type NotificationDelivery = 'away' | 'always';
export type NotificationTargetType = 'webhook' | 'bot';

export interface NotificationTarget {
	id: string;
	type: NotificationTargetType;
	enabled: boolean;
	events: ChatNotificationEvent[];
	delivery: NotificationDelivery;
	config: {
		url_masked?: string;
		bot_id?: string;
		destination_chat_id?: string;
	};
	created_at: number;
	updated_at: number;
}

export interface BotOption {
	id: string;
	name: string;
	platform: string;
	is_active: boolean;
	is_running: boolean;
}

export interface NotificationTargetPayload {
	id?: string;
	type?: NotificationTargetType;
	enabled?: boolean;
	events?: ChatNotificationEvent[];
	delivery?: NotificationDelivery;
	config?: Record<string, string>;
}

export async function listNotificationTargets(): Promise<NotificationTarget[]> {
	const data = await fetchJSON<{ targets: NotificationTarget[] }>('/api/notifications/targets');
	return data.targets;
}

export function createNotificationTarget(payload: NotificationTargetPayload) {
	return fetchJSON<NotificationTarget>('/api/notifications/targets', jsonBody(payload));
}

export function updateNotificationTarget(id: string, payload: NotificationTargetPayload) {
	return fetchJSON<NotificationTarget>(`/api/notifications/targets/${id}`, {
		...jsonBody(payload),
		method: 'PUT'
	});
}

export function deleteNotificationTarget(id: string) {
	return fetchJSON<{ ok: boolean }>(`/api/notifications/targets/${id}`, { method: 'DELETE' });
}

export function testNotificationTarget(id: string) {
	return fetchJSON<{ ok: boolean }>(`/api/notifications/targets/${id}/test`, { method: 'POST' });
}

export async function listNotificationBotOptions(): Promise<BotOption[]> {
	const data = await fetchJSON<{ bots: BotOption[] }>('/api/notifications/bot-options');
	return data.bots;
}
