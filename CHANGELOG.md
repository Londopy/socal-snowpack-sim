# Changelog

All notable changes to socal-snowpack-sim are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html). The section for a version is
what appears on its GitHub release page.

## [Unreleased]

### Added

- The model is now an importable package, `socal_snowpack`, with every threshold in `params.toml`.
- An hourly version of the model with a layer stack, terrain shading and a snow-level uncertainty
  band, checked against the daily model over 30 simulated winters.

### Fixed

- The tour card no longer covers the winter timeline on phones and tablets, or the day line on desktop.

## [0.1.0] - 2026-11-23

### Added

- Terrain analysis for 34 Southern California ski-touring peaks from USGS 3DEP elevation.
- A daily snowpack model run over 400 simulated winters, with storm slab, wind slab, wet,
  persistent slab, ice, freeze-thaw and corn by aspect and elevation.
- Figures, per-peak results and the README write-up.
- A 3D viewer at londo.me/socal-snowpack-sim: the three ranges and every peak on real terrain,
  painted relief, satellite, USGS topo, lidar hillshade, slope and aspect views, and dry,
  typical and big simulated winters played back day by day.
- Freeze-thaw view with an illustrated day clock, freeze-thaw charts and per-peak cycle counts.
- `src/export_site.py`, which builds the viewer's terrain, lidar hillshade and winter data.

[Unreleased]: https://github.com/Londopy/socal-snowpack-sim/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Londopy/socal-snowpack-sim/releases/tag/v0.1.0
