# Tareas — Vaquita v1

Cada tarea = un commit con tests verdes (`uv run pytest`, `ruff`, `mypy`).

## Fase 1 — Base
- [x] 1. Esqueleto: `pyproject`, ruff, mypy, pytest, app FastAPI mínima, CI, licencia. *Verifica: `pytest` y CI verdes.*
- [x] 2. `dominio/dinero`: centavos, parseo `"12.500,50"`, formato `$ 12.500,50`. *TDD.*
- [x] 3. `dominio/division`: iguales, exactos, porcentajes, partes; reparto determinista de centavos. *TDD + Hypothesis.*
- [x] 4. `dominio/saldos` y `dominio/deudas`: saldos, simplificar, no simplificar. *TDD + Hypothesis (5 invariantes).*
- [x] 5. `dominio/cotizacion`: conversión con cotización guardada. *TDD.*

### Checkpoint 1: dominio ≥ 95 % de cobertura, mypy estricto limpio.

## Fase 2 — Rebanadas verticales
- [x] 6. Datos: modelos, sesión, migración inicial Alembic.
- [x] 7. Crear grupo + cookie firmada + CSRF + cabeceras + base visual (tokens, fuentes).
- [x] 8. Invitación por link, elegir/agregar miembro, revocar link.
- [x] 9. Cargar gasto (camino rápido + avanzado) y lista, con HTMX.
- [x] 10. Editar, borrar e historial.
- [x] 11. Pagos, saldos, la libreta y saldar (alias, WhatsApp, tachado).

### Checkpoint 2: flujo crear → invitar → cargar → saldar funciona en el navegador.

- [x] 12. Cotizaciones: cliente API, caché, tipo de dólar, carga manual.
- [x] 13. Gastos fijos mensuales (generación perezosa idempotente).
- [x] 14. Resumen con gráficos SVG del servidor.
- [x] 15. Exportar CSV, XLSX y PDF.
- [x] 16. Demo "Viaje a Bariloche" + borrado automático.
- [x] 17. Rate limiting + tests de aislamiento entre grupos.
- [x] 18. Cuentas opcionales (Argon2) y "tus grupos".

### Checkpoint 3: todas las funcionalidades de la spec.

## Fase 3 — Terminación
- [x] 19. E2E Playwright celular/escritorio + axe.
- [x] 20. Capturas, crítica de diseño y correcciones; modo oscuro.
- [x] 21. Performance y Lighthouse; pantalla de "despertando".
- [x] 22. README, ADRs, GUIA-DESPLIEGUE.md (hosting verificado).
- [x] 23. Revisión de código y checklist de lanzamiento.
