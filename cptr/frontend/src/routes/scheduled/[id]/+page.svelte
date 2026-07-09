<script lang="ts">
	import { page } from '$app/stores';
	import AutomationsPanel from '$lib/components/automations/AutomationsPanel.svelte';
	import { t } from '$lib/i18n';

	const automationId = $derived($page.params.id);
</script>

<svelte:head>
	<title>{$t('automations.automation')} / Computer</title>
</svelte:head>

<AutomationsPanel {automationId} />
