import adapter from '@sveltejs/adapter-static';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

// pywebview serves ui/build from a local http server; hash routes need no server logic.
export default defineConfig({
	plugins: [
		sveltekit({
			adapter: adapter({ pages: 'build', assets: 'build', fallback: 'index.html' }),
			router: { type: 'hash' }
		})
	]
});
