// Use the FULL plotly.js build so every chart type renders (violin, treemap,
// sankey, radar, parcoords, splom, funnel, waterfall, heatmap, etc.).
// Bundle size is acceptable in a desktop app, and it avoids charts silently
// degrading to a plain bar chart for unsupported trace types.
import Plotly from 'plotly.js/dist/plotly.js';
export default Plotly;
