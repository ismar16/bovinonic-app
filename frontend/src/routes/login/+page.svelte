<script lang="ts">
    import { goto } from '$app/navigation';
    import { page } from '$app/state';
    import { Eye, EyeOff, LockKeyhole, ArrowRight } from 'lucide-svelte';
    import { login, me, ApiError } from '$lib/api';
    import { acceptUser } from '$lib/session';
    import { errorMessage } from '$lib/forms';
    import { syncNow } from '$lib/sync';
    import CattleMark from '$lib/components/CattleMark.svelte';
    import Notice from '$lib/components/Notice.svelte';
    let username = $state(''); let password = $state(''); let visible = $state(false); let error = $state(''); let loading = $state(false);
    async function submit(event: SubmitEvent) {
        event.preventDefault(); if (loading) return; loading = true; error = '';
        try {
            await login(username.trim(),password); await acceptUser(await me()); await syncNow();
            const target = page.url.searchParams.get('next');
            await goto(target?.startsWith('/') && !target.startsWith('//') && !target.startsWith('/login') ? target : '/');
        } catch (cause) { error = cause instanceof ApiError && cause.statusCode === 401 ? 'Usuario o contraseña incorrectos. Revisá ambos e intentá otra vez.' : errorMessage(cause, 'No se pudo conectar con la finca. Revisá tu conexión.'); }
        finally { loading = false; }
    }
</script>
<svelte:head><title>Ingresar · Bovinonic</title></svelte:head>
<div class="mx-auto max-w-md py-10 sm:py-16"><div class="mb-8 flex items-center gap-3"><span class="flex h-12 w-12 items-center justify-center rounded-xl bg-[#214c36] text-[#d4c79a]"><CattleMark class="h-8 w-8" /></span><span><span class="block font-serif text-3xl">Bovinonic</span><span class="eyebrow">Gestión de tu finca</span></span></div>
<section class="panel space-y-6 p-6 sm:p-8"><header><p class="eyebrow">Bienvenido a tu finca</p><h1 class="mt-3 font-serif text-3xl">Todo empieza con un buen registro.</h1><p class="page-description">Ingresá para consultar tu hato y continuar el trabajo del día.</p></header><form onsubmit={submit} class="space-y-5"><label class="field-label">Usuario<input class="field" bind:value={username} autocomplete="username" required  /></label><label class="field-label">Contraseña<span class="relative block"><input class="field pr-12" bind:value={password} type={visible ? 'text' : 'password'} autocomplete="current-password" required /><button type="button" class="absolute inset-y-0 right-1 flex min-w-10 items-center justify-center text-[#8b9a7c]" aria-label={visible ? 'Ocultar contraseña' : 'Mostrar contraseña'} aria-pressed={visible} onclick={() => visible = !visible}>{#if visible}<EyeOff class="h-4 w-4" />{:else}<Eye class="h-4 w-4" />{/if}</button></span></label><Notice tone="error" message={error} /><button class="action-button w-full" type="submit" disabled={loading}>{loading ? 'Ingresando…' : 'Ingresar a la finca'}<ArrowRight class="h-4 w-4" /></button></form><p class="flex items-start gap-2 text-xs leading-5 text-[#89977b]"><LockKeyhole class="mt-1 h-3.5 w-3.5 shrink-0" />Si olvidaste tu contraseña, contactá al administrador. El primer ingreso en este dispositivo requiere conexión.</p></section></div>
