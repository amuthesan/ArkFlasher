# Changelog

All notable changes to ArkFlasher will be documented in this file.

## [0.1.0]
- Stacked right panes vertically for Board Catalog, README, and Terminal Console.
- Auto-detect workspace and open with project data upon startup.

## [0.1.1]
- Selected board state highlights card frames dynamically.

## [0.1.2]
- Asynchronous GitHub release loading and fetching.
- Direct zipball downloading and import overrides.

## [0.1.3] - 2026-06-29
### Added
- Horizontal scrolling support inside Board Catalog Browser using a `tk.Canvas` container and a `ttk.Scrollbar`.
- Cross-platform mouse-wheel and trackpad horizontal scrolling propagation (macOS, Windows, Linux).
- Automatic scroll region and canvas height adjustment when catalog loads.

### Changed
- Renamed project template folder `mock_project` to `project_template` for clean, production-ready release distribution.
- Refactored `test_app.py` suite to dynamically resolve template workspace paths and reference `project_template` instead of hardcoded paths.
