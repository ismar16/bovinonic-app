<script lang="ts">
	import { goto } from '$app/navigation';
	import { login, me } from '$lib/api';
	import { currentFarm, sessionUser } from '$lib/stores';
	import { syncNow } from '$lib/sync';

	let username = $state('');
	let password = $state('');
	let error = $state('');
	let loading = $state(false);

	async function handleSubmit(event: SubmitEvent) {
		event.preventDefault();
		loading = true;
		error = '';
		try {
			await login(username, password);
			const user = await me();
			sessionUser.set({ id: user.id, username: user.username });
			if (user.farms.length > 0) {
				const first = user.farms[0];
				currentFarm.set({ id: first.farm, name: first.farm_name, role: first.role });
				await syncNow();
			}
			await goto('/');
		} catch {
			error = 'Usuario o contraseña incorrectos, o sin conexión.';
		} finally {
			loading = false;
		}
	}
</script>

<svelte:head><title>Iniciar sesión · Gestión Ganadera</title></svelte:head>

<div class="pt-12">
	<h1 class="mb-8 text-center text-3xl font-extrabold">Gestión Ganadera</h1>
	<form onsubmit={handleSubmit} class="flex flex-col gap-4">
		<label class="flex flex-col gap-1 font-bold">
			Usuario
			<input
				bind:value={username}
				required
				autocomplete="username"
				class="h-14 rounded-md border-2 border-black px-4 text-xl"
			/>
		</label>
		<label class="flex flex-col gap-1 font-bold">
			Contraseña
			<input
				bind:value={password}
				type="password"
				required
				autocomplete="current-password"
				class="h-14 rounded-md border-2 border-black px-4 text-xl"
			/>
		</label>
		{#if error}
			<p class="rounded-md border-2 border-red-700 bg-red-50 p-3 font-bold text-red-700">
				{error}
			</p>
		{/if}
		<button
			type="submit"
			disabled={loading}
			class="h-14 w-full rounded-md bg-green-700 text-xl font-extrabold text-white disabled:opacity-50"
		>
			{loading ? 'Ingresando…' : 'Ingresar'}
		</button>
	</form>
</div>
