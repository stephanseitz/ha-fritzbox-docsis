# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Sensors for the cable sync rate (downstream / upstream), taken from the last
  "cable available" entry in the event log; the last known value is kept when the
  entry rotates out of the log.

## [1.0.0] – 2026-10-03

First public release.

### Added

- Config flow with URL normalisation (local address or MyFRITZ!), re-authentication and
  options (polling interval 60–3600 s, event log on/off).
- Login via `login_sid.lua?version=2` with PBKDF2, MD5 fallback and transparent re-login.
- Per-channel sensors for DOCSIS 3.0 and 3.1 downstream and upstream, keyed by frequency:
  power level, MSE/MER, correctable and uncorrectable errors, errors per hour.
- Device-wide sensors: power min/max, worst MSE/MER, totals and rates, worst channel with
  top 5, OFDMA modulation, channel counts.
- Sync loss detection from the FRITZ!Box event log (German and English texts):
  connection binary sensor, last sync loss, in sync since, losses in 24 h / 7 days.
- Bus events `fritzbox_docsis_sync_lost` and `fritzbox_docsis_sync_restored` with the
  original log timestamp, de-duplicated across restarts; event entity for the logbook.
- Fallback resync detection from counter resets when the event log is disabled.
- English and German translations for the UI, entity names and attributes.
- Diagnostics with credentials redacted.
- Example dashboard and automations in English and German.
- Stand-alone check script `tools/fritz_docsis_check.py` (Python 3.10+, no dependencies).
- Test suite against a simulated FRITZ!Box; CI with hassfest, HACS validation, ruff and pytest.

[1.0.0]: https://github.com/stephanseitz/ha-fritzbox-docsis/releases/tag/v1.0.0
