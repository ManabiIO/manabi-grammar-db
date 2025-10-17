# Manabi Grammar DB (vendor)

This repository stores a file-based "database" of grammar points (YAML + Markdown) compiled into a distributable SQLite file.

- Target language directories: `grammar-xx/`
- License: CC BY 4.0 (see `LICENSE`)
- Build: `mise run build-db`
- Lint: `mise run lint`
- Output artifacts: `dist/manabi-grammar.sqlite` and schemas in `dist/`
