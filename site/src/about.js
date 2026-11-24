export const aboutHTML = (n) => `
<p>This is the viewer for <a href="https://github.com/Londopy/socal-snowpack-sim">socal-snowpack-sim</a>, a terrain and snowpack
simulator for ${n} Southern California ski-touring peaks. The terrain is real. The winters are simulated.</p>

<h3>Not an avalanche forecast</h3>
<p>The weather is randomly generated, the snowpack rules are hand-tuned, and nothing here has been checked against field
data. It shows patterns to learn from. It cannot tell you whether a slope is safe. Avalanches, falls on ice and rockfall
kill people in these mountains: take an avalanche course, carry rescue gear and practise with it, read current
observations, and make your own decisions in the field. The nonprofit So Cal Snow Avalanche Center shares observations
and runs courses.</p>

<h3>What you are looking at</h3>
<ul>
  <li><b>Terrain:</b> USGS 3DEP elevation from the AWS Terrain Tiles, about 8 m per pixel around each peak (shown at about 14 m)
  and about 130 m for the range overview. Peak views are true scale; the overview is stretched vertically so the ranges read.</li>
  <li><b>Lidar hillshade:</b> rendered by the USGS 3DEP elevation service, which uses 1 m lidar wherever it has been flown.
  The painted relief borrows its fine detail.</li>
  <li><b>Satellite and topo:</b> USGS National Map imagery and topo basemaps, loaded live.</li>
  <li><b>Simulated snow and problems:</b> three winters from the repo's model (dry, typical and big: the 10th, 50th and 90th
  percentile of snowfall at 8,500-9,500 ft among its 400 simulated winters). The model works on 8 aspects and 5 elevation
  bands on a 38&deg; slope; the map blends those cells across the real slopes. Problems are only drawn on 30-50&deg;
  ground, where slab avalanches start. Thin hatching is below the model's elevated line (0.45), full hatching at or above
  it. Those cut-offs are the author's.</li>
</ul>

<h3>Limits</h3>
<ul>
  <li>The weather is made up, not fitted to station records, and the same weather falls on every range.</li>
  <li>It runs snowy: median simulated snowfall at 7,500-8,500 ft is about twice Mt. Baldy resort's reported average.</li>
  <li>All thresholds and rates are hand-set. The aspect and timing patterns are sturdier than the day counts.</li>
  <li>One slope angle and a daily time step. No terrain shading, trees, gullies, cornices or rockfall. It cannot see a
  slope that is safe at 8 am and dangerous at noon.</li>
  <li>The grid smooths the steepest pitches. Headwalls and chutes are steeper than they map.</li>
  <li>Below 6,600 ft the model has no band, so the map fades the snow out there.</li>
</ul>

<h3>Keys</h3>
<p>Drag to orbit, right-drag or two fingers to pan, scroll or pinch to zoom. Space plays and pauses, the arrow keys step a
day (Shift for a week), 1-6 switch map layers, Esc closes a panel or the tour.</p>

<h3>Credits and licences</h3>
<ul>
  <li>Elevation: Terrain Tiles on AWS Open Data, built from USGS 3DEP. Lidar hillshade, imagery and topo: USGS The National
  Map. US Government works, public domain.</li>
  <li>Peak list cross-checked against the Sierra Club Hundred Peaks Section list.</li>
  <li>Built with three.js and Vite (MIT, <a href="licenses/three.txt">three.js licence</a>). Type: Barlow and Barlow
  Condensed by Jeremy Tribby, <a href="licenses/barlow.txt">SIL Open Font License</a>.</li>
  <li>Code: MIT licence, by Londopy. Source, model and figures on
  <a href="https://github.com/Londopy/socal-snowpack-sim">GitHub</a>; report problems in its
  <a href="https://github.com/Londopy/socal-snowpack-sim/issues">issues</a>.</li>
</ul>
`;
