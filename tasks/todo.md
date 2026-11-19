# Tareas — Vaquita v1

Cada tarea = un commit con tests verdes (`uv run pytest`, `ruff`, `mypy`).

## Fase 1 — Base
- [ ] 1. Esqueleto: `pyproject`, ruff, mypy, pytest, app FastAPI mínima, CI, licencia. *Verifica: `pytest` y CI verdes.*
- [ ] 2. `dominio/dinero`: centavos, parseo `"12.500,50"`, formato `$ 12.500,50`. *TDD.*
- [ ] 3. `dominio/division`: iguales, exactos, porcentajes, partes; reparto determinista de centavos. *TDD + Hypothesis.*
- [ ] 4. `dominio/saldos` y `dominio/deudas`: saldos, simplificar, no simplificar. *TDD + Hypothesis (5 invariantes).*
- [ ] 5. `dominio/cotizacion`: conversión con cotización guardada. *TDD.*

### Checkpoint 1: dominio ≥ 95 % de cobertura, mypy estricto limpio.

## Fase 2 — Rebanadas verticales
- [ ] 6. Datos: modelos, sesión, migración inicial Alembic.
- [ ] 7. Crear grupo + cookie firmada + CSRF + cabeceras + base visual (tokens, fuentes).
- [ ] 8. Invitación por link, elegir/agregar miembro, revocar link.
- [ ] 9. Cargar gasto (camino rápido + avanzado) y lista, con HTMX.
- [ ] 10. Editar, borrar e historial.
- [ ] 11. Pagos, saldos, la libreta y saldar (alias, WhatsApp, tachado).

### Checkpoint 2: flujo crear → invitar → cargar → saldar funciona en el navegador.

- [ ] 12. Cotizaciones: cliente API, caché, tipo de dólar, carga manual.
- [ ] 13. Gastos fijos mensuales (generación perezosa idempotente).
- [ ] 14. Resumen con gráficos SVG del servidor.
- [ ] 15. Exportar CSV, XLSX y PDF.
- [ ] 16. Demo "Viaje a Bariloche" + borrado automático.
- [ ] 17. Rate limiting + tests de aislamiento entre grupos.
- [ ] 18. Cuentas opcionales (Argon2) y "tus grupos".

### Checkpoint 3: todas las funcionalidades de la spec.

## Fase 3 — Terminación
- [ ] 19. E2E Playwright celular/escritorio + axe.
- [ ] 20. Capturas, crítica de diseño y correcciones; modo oscuro.
- [ ] 21. Performance y Lighthouse; pantalla de "despertando".
- [ ] 22. README, ADRs, GUIA-DESPLIEGUE.md (hosting verificado).
- [ ] 23. Revisión de código y checklist de lanzamiento.
