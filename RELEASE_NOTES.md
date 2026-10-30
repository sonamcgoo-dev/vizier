# Vizier 1.0.1 — Cleanup and MCP bundle

This release focuses on repository cleanup and broader MCP/skills readiness.

## Included in this release

- Added a reusable default skill catalog for the application.
- Added a curated starter MCP server manifest bundle.
- Added documentation for bundled skills and common MCP server usage.
- Kept packaging metadata aligned with the new shipped assets.
- Updated the package version to 1.0.1.

## Notes

The bundled MCP examples are intentionally safe-by-default and disabled unless the
user explicitly enables them. This avoids accidental network or filesystem access.
