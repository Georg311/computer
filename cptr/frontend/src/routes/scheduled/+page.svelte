<script lang="ts">
	import { page } from '$app/stores';
	import AutomationsPanel from '$lib/components/automations/AutomationsPanel.svelte';
	import { t } from '$lib/i18n';

	const workspace = $derived($page.url.searchParams.get('workspace') || undefined);
</script>

<svelte:head>
	<title>{$t('automations.title')} / Computer</title>
</svelte:head>

<AutomationsPanel workspace={workspace} />
