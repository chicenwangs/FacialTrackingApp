<script lang="ts">
	import { goto } from '$app/navigation';
	import { call, live } from '#lib/api.svelte.js';

	let msg = $state('');
	const v = $derived(live.s?.vcam);

	async function register() {
		const r = await call('register_vcam');
		msg = r.ok ? 'Done. Restart FaceCam so it can send to FaceCam Camera.' : r.error;
	}
	async function finish() {
		await call('finish_setup');
		goto('#/');
	}
</script>

<section class="card setup">
	<div class="strip a"><h2>Set up FaceCam</h2></div>
	<div class="body">
		<h3>Add our camera to Windows</h3>
		<p>
			Your webcam was chosen automatically: <strong>{live.s?.camera ?? 'checking…'}</strong>.
		</p>
		<p>
			FaceCam creates its own camera called <strong>FaceCam Camera</strong> that Zoom, Discord, Teams, OBS
			and browsers can pick. Windows asks for admin permission once. You don't need OBS.
		</p>
		<p>Status: <strong>{v?.status ?? '…'}</strong></p>
		{#if msg}<p class="note" role="status">{msg}</p>{/if}
		<div class="row">
			<button class="btn" onclick={finish}>{v?.status === 'registered' ? 'Continue' : 'Skip for now'}</button>
			<button class="btn primary" onclick={register} disabled={v?.status === 'not installed'}
				>{v?.status === 'registered' ? 'Re-register' : 'Add camera (admin once)'}</button
			>
		</div>
		{#if v?.status === 'not installed'}<p class="quiet">
				The FaceCam camera DLL is missing. See native/softcam/README.md.
			</p>{/if}
	</div>
</section>

<style>
	.setup {
		max-width: 760px;
		margin: 0 auto;
	}
	h3 {
		margin-top: 0;
	}
</style>
