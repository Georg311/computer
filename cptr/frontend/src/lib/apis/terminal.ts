/**
 * Terminal API: create, list, delete sessions.
 */
import { fetchHandler, fetchJSON, jsonBody } from '$lib/apis';

export interface TerminalSession {
	session_id: string;
}

export interface CommandSession {
	command_session_id: string;
	task_id: string;
	workspace: string;
	chat_id: string | null;
	message_id: string | null;
	call_id: string | null;
	command: string;
	created_at: number;
	status: 'running' | 'completed';
	done: boolean;
	exit_code: number | null;
	total_bytes: number;
	output: string;
}

export const listSessions = () => fetchJSON<TerminalSession[]>('/api/terminal');

export const createSession = (cwd?: string) =>
	fetchJSON<TerminalSession>('/api/terminal', jsonBody(cwd ? { cwd } : {}));

export const deleteSession = (sessionId: string) =>
	fetchHandler(`/api/terminal/${sessionId}`, { method: 'DELETE' }).catch(() => {});

export const listCommandSessions = (workspace: string, chatId?: string | null) =>
	fetchJSON<CommandSession[]>(
		`/api/terminal/sessions?workspace=${encodeURIComponent(workspace)}${chatId ? `&chat_id=${encodeURIComponent(chatId)}` : ''}`
	);
