// Bridge to Python (window.pywebview.api) + live state pushed ~10/s via window.__sc.emit.

export type Live = {
	state: string;
	frozen: boolean;
	fps: Record<string, number>;
	camera: string;
	vcam: { status: string; live: boolean; connected: boolean };
	zoom: number;
	brightness: number;
	contrast: number;
};

export const live = $state<{ s: Live | null }>({ s: null });

window.__sc = { emit: (s) => (live.s = s) };

type Api = Record<string, (...args: any[]) => Promise<any>>;
let ready: Promise<Api> | null = null;

export function api(): Promise<Api> {
	ready ??= new Promise((resolve) => {
		if (window.pywebview?.api) return resolve(window.pywebview.api);
		window.addEventListener('pywebviewready', () => resolve(window.pywebview!.api), { once: true });
	});
	return ready;
}

export async function call<T = any>(name: string, ...args: unknown[]): Promise<T> {
	return (await api())[name](...args);
}

/** State in words (never colour only). */
export function stateWords(s: Live | null): string {
	if (!s) return 'Starting';
	return s.state.charAt(0).toUpperCase() + s.state.slice(1);
}
