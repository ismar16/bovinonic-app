<script lang="ts">
    import PageHeader from '$lib/components/PageHeader.svelte';
    import { catalogConfig } from '$lib/catalogs';
    import { MapPin, Users, Tag, ArrowUpRight } from 'lucide-svelte';
    const icons = { paddocks: MapPin, owners: Users, brands: Tag };
</script>
<svelte:head><title>Catálogos · Bovinonic</title></svelte:head>
<div class="workspace-page space-y-6"><PageHeader title="Los datos de tu finca" eyebrow="Catálogos" description="Cada catálogo tiene su propia vista para buscar, agregar y editar registros. Los cambios conservan las relaciones con los animales." backHref="/settings" backLabel="Ajustes" />
<div class="grid gap-4 md:grid-cols-3">{#each Object.entries(catalogConfig) as [key, config]}{@const Icon = icons[key as keyof typeof icons]}<a href="/catalogs/{key}" class="panel group p-6"><div class="mb-5 flex items-center justify-between"><Icon class="h-6 w-6 text-[#8da477]" /><ArrowUpRight class="h-4 w-4 text-[#a3b295]" /></div><h2 class="section-title">{config.title}</h2><p class="mt-3 text-sm leading-6 text-[#829174]">{config.description}</p><span class="mt-6 inline-block text-xs font-semibold text-[#456a3c]">Consultar catálogo →</span></a>{/each}</div></div>
