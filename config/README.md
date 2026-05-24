# config/

Reserved for environment-specific overrides that don't belong in code or
in `.env`. Currently empty by design.

## Where real configuration lives today

- **Runtime settings**: [../.env](../.env) → loaded by
  [../backend/core/config.py](../backend/core/config.py) via pydantic-settings.
- **Defaults for those settings**: [../backend/core/config.py](../backend/core/config.py)
- **Docker / compose**: [../docker-compose.yml](../docker-compose.yml)
- **Reverse proxy**: [../nginx/](../nginx/)
- **CI / lint configs**: live at the project root (`.eslintrc`, `tsconfig.json`, etc.)

## When to put something here

Use this directory for files that are **not** code, **not** secrets, but
need to ship alongside a deployment:

- Test-catalog YAML/CSV imports
- Reference-range tables for new disease panels
- Whitelisted SMS phone-number patterns per country
- Pilot-site overlays (hospital-specific defaults)

Keep secrets in `.env` / your secret manager — never here.
