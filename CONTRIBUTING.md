# Contributing to IPOEForge

## Development Setup

```bash
git clone git@github.com:tjdodson/IPOEForge.git
cd IPOEForge
uv sync
```

### System Dependencies

```bash
brew install gdal   # macOS
apt install gdal-bin  # Linux
```

## Running Tests

```bash
uv run pytest tests/ -v -m "not integration"  # unit tests
uv run ruff check                              # linting
uv run ruff check --fix                        # auto-fix
```

Integration tests require network access and download real data. They are marked with `@pytest.mark.integration` and skipped by default.

## Code Style

- Line length: 100 (ruff config in pyproject.toml)
- Import sorting: ruff handles this automatically
- No comments unless asked
- Follow existing patterns in the codebase

## Architecture

See `SPEC.md` for the full specification. Key decisions:

- **Output format:** Individual GeoTIFFs + QML styles (not GPKG)
- **Elevation source:** Direct SRTM download from AWS SKADi (not the `elevation` Python library)
- **MGRS grid:** QGIS native grid (not a generated layer)
- **Auth:** Public sources only in skill; PKI support exists but not exposed to agents

## Adding New Layers

1. Add the download/computation function in the appropriate module
2. Wire it into `__main__.py` with error handling (warn + skip on failure)
3. Add a QML style in `styles.py`
4. Add unit tests
5. Update SPEC.md with the new layer

## Commits

Keep commits focused. Use descriptive messages. No secrets or API keys.
