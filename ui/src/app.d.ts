declare global {
	interface Window {
		pywebview?: { api: Record<string, (...args: unknown[]) => Promise<any>> };
		__sc?: { emit: (s: Live) => void };
	}
	type Live = import('#lib/api.svelte.js').Live;
}
export {};
