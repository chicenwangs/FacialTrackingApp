<script lang="ts">
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { call, live, stateWords } from '#lib/api.svelte.js';

	let { children } = $props();
	const nav = [
		['/', 'Home'],
		['/settings', 'Settings']
	];
	const s = $derived(live.s);

	$effect(() => {
		call('get_state').then((st) => {
			if (st.vcam?.status !== 'registered' && page.url.hash !== '#/setup') goto('#/setup');
		});
	});

	function current(href: string): boolean {
		const h = page.url.hash.replace(/^#/, '') || '/';
		return href === '/' ? h === '/' : h.startsWith(href);
	}
</script>

<header>
	<strong class="logo">FaceCam</strong>
	<nav aria-label="Main">
		{#each nav as [href, label]}
			<a href={'#' + href} aria-current={current(href) ? 'page' : undefined}>{label}</a>
		{/each}
	</nav>
	<span class="chip" role="status" aria-live="polite">
		{stateWords(s)}{s?.fps?.output ? ` · ${Math.round(s.fps.output)} fps` : ''}
	</span>
	<span class="chip">McG Cam · {s?.vcam?.status ?? '…'}{s?.vcam?.connected ? ' · in use' : ''}</span>
	<button class="btn" onclick={() => call('quit')}>Quit</button>
</header>
<main>{@render children()}</main>

<style>
	header {
		display: flex;
		align-items: center;
		gap: 12px;
		flex-wrap: wrap;
		padding: 14px 20px;
	}
	.logo {
		font-size: 20px;
		margin-right: 8px;
	}
	nav {
		display: flex;
		gap: 4px;
		flex: 1;
	}
	nav a {
		text-decoration: none;
		font-weight: 600;
		padding: 6px 14px;
		min-height: 24px;
		border-radius: 999px;
		border: 1.5px solid transparent;
	}
	nav a[aria-current='page'] {
		background: var(--card);
		border-color: var(--edge);
	}
	main {
		padding: 4px 20px 24px;
	}
</style>
