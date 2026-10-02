# Contributing

Thanks for helping! Issues and pull requests in English or German are welcome.

## Reporting a problem

Please include:

- FRITZ!Box model, FRITZ!OS version and cable provider
- Home Assistant and integration version
- The **diagnostics** file (*Settings › Devices & services › FRITZ!Box Cable (DOCSIS) ›
  ⋮ › Download diagnostics*). Credentials are removed automatically.

If the integration cannot be set up at all, the output and `fritz_docsis_raw.json` of
`tools/fritz_docsis_check.py` help a lot. Do not post passwords or your MyFRITZ! address.

## Development setup

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements_test.txt
pytest
ruff check . && ruff format --check .
```

Python 3.13 is required (same as Home Assistant). The tests run against
`tests/mock_fritzbox.py`, a small aiohttp server that mimics `login_sid.lua` and
`data.lua`. If your box returns a different JSON layout, add it there as a variant and
write a test for it in `tests/test_parser.py`.

## Guidelines

- Keep `custom_components/fritzbox_docsis/parser.py` free of Home Assistant imports, so
  the check script keeps working without Home Assistant.
- New entities need a `translation_key` with names in `strings.json`,
  `translations/en.json` and `translations/de.json`.
- Do not change entity unique IDs; users' history depends on them.
- Add an entry to `CHANGELOG.md` under *Unreleased*.

## Releasing

1. Update the version in `custom_components/fritzbox_docsis/manifest.json`,
   `pyproject.toml` and `CHANGELOG.md`.
2. Create a GitHub release with tag `vX.Y.Z`. The release workflow attaches
   `fritzbox_docsis.zip`, and HACS picks up the new version.
