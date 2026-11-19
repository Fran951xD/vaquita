# ADR-0002: SQLite en local, PostgreSQL en CI y producción

Estado: aceptada · 2026-11-19

## Contexto

Quien revisa el portfolio tiene que poder correr el proyecto en tres comandos, sin instalar Docker ni una base. Pero producción usa PostgreSQL, y "en mi máquina anda" con otra base es un riesgo.

## Decisión

- Desarrollo local y tests rápidos: SQLite en un archivo (`vaquita.db`). Cero instalación.
- CI: la misma suite de integración corre dos veces, contra SQLite y contra un Postgres 17 de servicio (`VAQUITA_TEST_DATABASE_URL`).
- Producción: PostgreSQL gratis en Neon.
- El esquema se crea siempre con las migraciones de Alembic (también en los tests), y un test compara las migraciones con los modelos.
- Para que las dos bases devuelvan exactamente lo mismo, los `Decimal` y las fechas con zona se guardan como texto (`DecimalTexto`, `FechaHoraUTC`). SQLite no tiene `NUMERIC` exacto ni guarda zonas horarias.
- No hay SQL crudo: todo pasa por SQLAlchemy 2.0.

## Consecuencias

- Cualquiera prueba el proyecto con `uv sync`, `uv run alembic upgrade head` y `uv run uvicorn vaquita.web.app:crear_app --factory --reload`.
- Las diferencias entre motores se detectan en CI, no en producción.
- Las migraciones usan `render_as_batch` porque SQLite no soporta todos los `ALTER TABLE`.
