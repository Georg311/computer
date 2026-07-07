/**
 * Chat API: send messages, approve/reject tools, cancel tasks, fetch chats.
 */
import { fetchJSON, jsonBody } from '$lib/apis';

export interface ChatMessageRow {
	id: string;
	parent_id: string | null;
	role: 'user' | 'assistant';
	content: string;
	model: string | null;
	done: boolean;
	output: any[] | null;
	usage: Record<string, number> | null;
	meta: Record<string, any> | null;
	created_at: number;
}

export interface ChatInfo {
	id: string;
	title: string;
	summary: string | null;
	folder: string;
	meta: Record<string, any> | null;
	current_message_id: string | null;
	created_at: number;
	updated_at: number;
	is_active?: boolean;
}

export interface ContextUsage {
	tokens: number;
	estimated_tokens: number;
	threshold: number;
	percent: number;
	source: 'estimated';
}

export type TaskStatus = 'pending' | 'in_progress' | 'completed' | 'cancelled';

export interface ChatTask {
	id: string;
	content: string;
	status: TaskStatus;
}

export interface ChatDetail {
	chat: ChatInfo;
	messages: ChatMessageRow[];
	tasks?: ChatTask[];
	context_usage?: ContextUsage | null;
}

export interface SendMessageResult {
	chat_id: string;
	message_id: string;
	queued?: boolean;
	user_message?: ChatMessageRow;
	assistant_message?: ChatMessageRow;
}

export interface ChatSendParams {
	tool_approval_mode?: string;
	plan_mode?: boolean;
	request_params?: Record<string, unknown>;
	voice_mode?: boolean;
}

export interface CompactChatResult {
	ok: boolean;
	compacted: boolean;
	reason?: string;
	dropped_messages?: number;
	kept_messages?: number;
	summary_chars?: number;
	context_usage?: ContextUsage | null;
}

// ── Queries ─────────────────────────────────────────────────

export const getChats = (
	workspace: string,
	limit = 50,
	offset = 0,
	sortBy: 'title' | 'updated_at' = 'updated_at',
	sortDir: 'asc' | 'desc' = 'desc'
) =>
	fetchJSON<{ chats: ChatInfo[]; total: number; has_more: boolean }>(
		`/api/chats?workspace=${encodeURIComponent(workspace)}&limit=${limit}&offset=${offset}&sort_by=${sortBy}&sort_dir=${sortDir}`
	);

export const getChat = (chatId: string, modelId?: string) => {
	const suffix = modelId ? `?model_id=${encodeURIComponent(modelId)}` : '';
	return fetchJSON<ChatDetail>(`/api/chats/${chatId}${suffix}`);
};

export const deleteChat = (chatId: string) =>
	fetchJSON<{ ok: boolean }>(`/api/chats/${chatId}`, { method: 'DELETE' });

export const forkChat = (chatId: string, messageId?: string | null) =>
	fetchJSON<{ ok: boolean; chat_id: string }>(
		`/api/chats/${chatId}/fork`,
		jsonBody({ message_id: messageId ?? null })
	);

// ── Mutations ───────────────────────────────────────────────

export const sendMessage = (
	content: string,
	modelId: string,
	workspace: string,
	chatId?: string,
	parentId?: string | null,
	params: ChatSendParams = {},
	regenerationPrompt?: string,
	files?: { id: string; name: string; url: string; type: string }[]
) =>
	fetchJSON<SendMessageResult>(
		'/api/chats',
		jsonBody({
			content,
			model_id: modelId,
			workspace,
			chat_id: chatId,
			parent_id: parentId ?? null,
			regeneration_prompt: regenerationPrompt,
			files: files ?? [],
			params
		})
	);

export const approveToolCall = (
	chatId: string,
	messageId: string,
	callId: string,
	approved = true
) =>
	fetchJSON(
		`/api/chats/${chatId}/messages/${messageId}/approve`,
		jsonBody({ call_id: callId, approved })
	);

export const cancelTask = (chatId: string, messageId: string) =>
	fetchJSON(`/api/chats/${chatId}/messages/${messageId}/cancel`, { method: 'POST' });

export const compactChat = (chatId: string, modelId: string) =>
	fetchJSON<CompactChatResult>(`/api/chats/${chatId}/compact`, jsonBody({ model_id: modelId }));

export const updateCurrentMessage = (chatId: string, messageId: string) =>
	fetchJSON<{ ok: boolean }>(`/api/chats/${chatId}/current`, jsonBody({ message_id: messageId }));

export const updateMessage = (
	chatId: string,
	messageId: string,
	updates: { content?: string; output?: any[] }
) =>
	fetchJSON<{ ok: boolean }>(`/api/chats/${chatId}/messages/${messageId}`, {
		method: 'PATCH',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(updates)
	});

export const createMessage = (
	chatId: string,
	parentId: string | null,
	role: string,
	content: string,
	output?: any[]
) =>
	fetchJSON<{ ok: boolean; message_id: string }>(
		`/api/chats/${chatId}/messages`,
		jsonBody({ parent_id: parentId, role, content, output })
	);

// ── Queue management ────────────────────────────────────────

export const queueSendNow = (chatId: string, messageId: string) =>
	fetchJSON<{ ok: boolean; chat_id: string; message_id: string }>(
		`/api/chats/${chatId}/queue/${messageId}/send`,
		{ method: 'POST' }
	);

export const queueDelete = (chatId: string, messageId: string) =>
	fetchJSON<{ ok: boolean }>(`/api/chats/${chatId}/queue/${messageId}`, { method: 'DELETE' });
