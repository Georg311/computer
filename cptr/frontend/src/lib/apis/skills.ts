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
}

export const getSkills = (workspace: string) =>
	fetchJSON<SkillInfo[]>(`/api/skills?workspace=${encodeURIComponent(workspace)}`);
