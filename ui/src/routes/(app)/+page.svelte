<script lang="ts">
	import { call, live, stateWords } from '#lib/api.svelte.js';

	let mode = $state<'output' | 'camera'>('output');
	let urls = $state<{ camera: string; output: string } | null>(null);
	let visible = $state(document.visibilityState === 'visible');
	let zoom = $state(1);
	const s = $derived(live.s);

	$effect(() => {
		call('get_state').then((st) => {
			urls = st.preview;
			zoom = st.zoom;
		});
		const onVis = () => (visible = document.visibilityState === 'visible');
		document.addEventListener('visibilitychange', onVis);
		return () => document.removeEventListener('visibilitychange', onVis);
	});
</script>

<div class="grid">
	<section class="card">
		<div class="strip a">
			<h2>Live preview</h2>
			<div class="seg" role="group" aria-label="Preview source">
				<button aria-pressed={mode === 'camera'} onclick={() => (mode = 'camera')}>Camera</button>
				<button aria-pressed={mode === 'output'} onclick={() => (mode = 'output')}>Output</button>
			</div>
		</div>
		<div class="preview">
			{#if urls && visible}
				<img src={urls[mode]} alt={mode === 'camera' ? 'Camera with face box' : 'What apps see'} />
			{:else}
				<p>Preview paused while hidden.</p>
			{/if}
		</div>
		<div class="body row">
			<span class="chip">{stateWords(s)}</span>
			<button class="btn" onclick={() => call('toggle_freeze')}
				>{s?.frozen ? 'Resume framing' : 'Freeze framing'}</button
			>
			{#if s?.fps?.output}<span class="chip">{s.fps.output} fps out</span>{/if}
			<label class="row">
				Zoom
				<input
					type="range"
					min="0.5"
					max="2"
					step="0.1"
					bind:value={zoom}
					onchange={() => call('set_zoom', zoom)}
				/>
				<span>{Number(zoom).toFixed(1)}×</span>
			</label>
		</div>
		<p class="body quiet small">The preview runs at 30 fps. The virtual camera also stays at 30 fps.</p>
	</section>

	<section class="card">
		<div class="strip b"><h2>Status</h2></div>
		<dl class="body">
			<dt>Virtual camera</dt>
			<dd>
				FaceCam Camera · {s?.vcam?.status ?? '…'}{s?.vcam?.connected ? ' · in use' : ''}
				{#if s && s.vcam.status !== 'registered'}<a href="#/settings">Set up</a>{/if}
			</dd>
			<dt>Webcam</dt>
			<dd>{s?.camera ?? '…'}</dd>
			<dt>Stages</dt>
			<dd class="quiet">
				{#each Object.entries(s?.fps ?? {}) as [k, v]}<span>{k} {v} fps · </span>{/each}
			</dd>
		</dl>
	</section>
</div>

<style>
	.grid {
		display: grid;
		grid-template-columns: minmax(0, 2fr) minmax(0, 1fr);
		gap: 20px;
	}
	.preview {
		background: var(--preview-bg);
		aspect-ratio: 16 / 9;
		display: grid;
		place-items: center;
	}
	.preview img {
		width: 100%;
		height: 100%;
		object-fit: contain;
	}
	.preview p {
		color: var(--primary-ink);
	}
	dl {
		margin: 0;
		display: grid;
		grid-template-columns: auto 1fr;
		gap: 8px 12px;
	}
	dt {
		font-weight: 600;
	}
	dd {
		margin: 0;
	}
	.small {
		font-size: 12px;
		margin: 0;
	}
</style>
