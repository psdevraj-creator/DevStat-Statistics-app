import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: '../backend/static',
    emptyOutDir: true,
    /* NOTE: we intentionally do NOT alias 'plotly.js/dist/plotly' to the
       cartesian-only build. The full bundle (set in src/plotly-setup.ts) is
       required so every chart type renders correctly. */
  },
})
