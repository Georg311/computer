/**
 * Skills API: list available skills for the $ mention picker.
 */
import { fetchJSON } from '$lib/apis';

export interface SkillInfo {
	name: string;
	description: string;
	location: string;
	source: string; // "workspace" | "global"
	license?: string;
	compatibility?: string;
	managed?: boolean;
	created_by?: string | null;
	created_from?: string | null;
	view_count?: number;
	use_count?: number;
	update_count?: number;
	last_viewed_at?: string | null;
	last_used_at?: string | null;
	last_updated_at?: string | null;
}

export const getSkills = (workspace?: string) =>
	fetchJSON<SkillInfo[]>(
		workspace ? `/api/skills?workspace=${encodeURIComponent(workspace)}` : '/api/skills'
	);
