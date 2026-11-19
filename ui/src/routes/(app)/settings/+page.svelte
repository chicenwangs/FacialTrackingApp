<script lang="ts">
	import { call, live } from '#lib/api.svelte.js';

	type S = Record<string, any>;
	let s = $state<S | null>(null);
	let cameras = $state<number[]>([]);
	let msg = $state<{ ok: boolean; text: string } | null>(null);
	const v = $derived(live.s?.vcam);

	$effect(() => {
		call('get_settings').then((x) => (s = x));
		call('list_cameras').then((x) => (cameras = x));
	});

	async function save() {
		const r = await call('save_settings', $state.snapshot(s));
		msg = r.ok ? { ok: true, text: 'Saved.' } : { ok: false, text: r.error };
		if (r.ok) s = r.settings;
	}
	async function vcam(register: boolean) {
		const r = await call(register ? 'register_vcam' : 'unregister_vcam');
		msg = r.ok
			? { ok: true, text: 'Windows asked for admin permission. Restart FaceCam after it finishes.' }
			: { ok: false, text: r.error };
	}
</script>

{#if s}
	<form
		class="grid"
		onsubmit={(e) => {
			e.preventDefault();
			save();
		}}
	>
		<section class="card">
			<div class="strip a"><h2>Camera &amp; framing</h2></div>
			<div class="body fields">
				<label>
					<span><strong>Webcam</strong></span>
					<select bind:value={s.camera}>
						{#each cameras as c}<option value={c}>Camera {c}</option>{/each}
					</select>
					<output>{live.s?.camera ?? ''}</output>
				</label>
				<label>
					<span><strong>Zoom</strong><br /><span class="quiet">Face size in the frame.</span></span>
					<input type="range" min="0.5" max="2" step="0.1" bind:value={s.zoom} />
					<output>{Number(s.zoom).toFixed(1)}×</output>
				</label>
				<label>
					<span><strong>Brightness</strong></span>
					<input type="range" min="0" max="100" step="1" bind:value={s.brightness} />
					<output>{s.brightness}</output>
				</label>
				<label>
					<span><strong>Contrast</strong></span>
					<input type="range" min="0" max="100" step="1" bind:value={s.contrast} />
					<output>{s.contrast}</output>
				</label>
			</div>
		</section>

		<section class="card">
			<div class="strip b"><h2>Our virtual camera</h2></div>
			<div class="body">
				<p>
					Status: <strong>{v?.status ?? '…'}</strong>{v?.live ? ' · sending' : ''}{v?.connected
						? ' · in use by an app'
						: ''}
				</p>
				<p class="quiet">
					FaceCam creates its own camera called <strong>McG Cam</strong> (DirectShow, 64-bit). Apps
					pick it directly — you do not need OBS. Registering needs admin once.
				</p>
				<div class="row">
					<button type="button" class="btn" onclick={() => vcam(true)}
						>{v?.status === 'registered' ? 'Re-register' : 'Register McG Cam'}</button
					>
					<button
						type="button"
						class="btn danger"
						onclick={() => vcam(false)}
						disabled={v?.status !== 'registered'}>Unregister</button
					>
				</div>
			</div>
		</section>

		<div class="actions row">
			<button class="btn primary" type="submit">Save settings</button>
			{#if msg}<p class="note" class:ok={msg.ok} class:alert={!msg.ok} role="status">
					{msg.text}
				</p>{/if}
		</div>
	</form>
{/if}

<style>
	.grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(380px, 1fr));
		gap: 20px;
		align-items: start;
	}
	.fields {
		display: grid;
		gap: 14px;
	}
	.fields label {
		display: grid;
		grid-template-columns: minmax(0, 1fr) 160px 70px;
		gap: 10px;
		align-items: center;
	}
	.actions {
		grid-column: 1 / -1;
	}
</style>
