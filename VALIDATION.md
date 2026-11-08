# Validation

- The included JavaScript check suite passed 577 checks covering known calculations, missing values, return alignment/correlation, histograms, CSV round trips, source provenance, all practice symbols/windows, and UI references.
- All 10 Python API unit tests passed, covering schema, validation, cache timing, CSV output, provider failure without simulated fallback, credential-free read-only CORS, and static configuration. These tests use explicitly labelled fixtures.
- A separate actual Yahoo integration request through FastAPI returned HTTP 200 and 390 AAPL one-minute bars, with the last returned bar stamped 2026-11-06 at 15:59 US Eastern. The request took about 7.5 seconds. This verifies one retrieval, not future uptime or exchange-level real-time availability.
- Browser checks verified practice charts, comparison statistics, investigation/share controls, CSV and text downloads, local CSV import with source-unverified labelling, desktop/phone layouts, and the teacher guide. The browser-exported practice CSV contained 260 rows, each labelled SIMULATED.
- The preview's service health page was reachable, but its Yahoo chart request did not complete during browser QA. Actual retrieval was verified independently through the Python API; the public front-end/service connection must be checked after deployment on the owner's accounts.
- No GitHub Pages or Render deployment was performed. No credentials are included.
