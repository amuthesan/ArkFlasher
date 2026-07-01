# Changelog

All notable changes to ArkFlasher will be documented in this file.

## [1.0.0] - 2026-07-01
### Added
- Native ESP32-S3 Standalone Flasher Host firmware (`firmware/`).
- USB Host CDC-ACM driver mapping and low-level `esp-serial-flasher` integration.
- Responsive HTML5 Single Page Application (SPA) dashboard served from flash memory.
- Wi-Fi Access Point (`ArkFlasher_AP` at `192.168.4.1`) and lightweight REST HTTP server.
- Real-time event log stream console powered by Server-Sent Events (SSE).
- Dynamic file segment addressing and chunked binary flashing.

## [0.1.3] - 2026-06-29
### Added
- Horizontal scrolling support inside Board Catalog Browser using a `tk.Canvas` container and a `ttk.Scrollbar`.
- Cross-platform mouse-wheel and trackpad horizontal scrolling propagation (macOS, Windows, Linux).
- Automatic scroll region and canvas height adjustment when catalog loads.

### Changed
- Renamed project template folder `mock_project` to `project_template` for clean, production-ready release distribution.
- Refactored `test_app.py` suite to dynamically resolve template workspace paths and reference `project_template` instead of hardcoded paths.
