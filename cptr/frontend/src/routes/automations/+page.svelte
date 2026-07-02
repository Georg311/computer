<script lang="ts">
	import AutomationsPanel from '$lib/components/automations/AutomationsPanel.svelte';
	import { t } from '$lib/i18n';
</script>

<svelte:head>
	<title>{$t('automations.title')} / Computer</title>
</svelte:head>

<AutomationsPanel />
