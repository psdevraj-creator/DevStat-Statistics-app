import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      // Use the slimmer cartesian-only build (scatter, bar, box, histogram, line)
      // instead of the full 10 MB plotly.js. Saves ~3 MB in the production bundle.
      'plotly.js/dist/plotly': 'plotly.js/dist/plotly-cartesian.js',
    },
  },
  build: {
    outDir: '../backend/static',
    emptyOutDir: true,
  },
})
