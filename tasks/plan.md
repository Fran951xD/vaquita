# Plan de implementación: Vaquita v1

Spec: [SPEC.md](../SPEC.md) · Diseño: [DISENO.md](../DISENO.md) · Tareas: [todo.md](todo.md)

## Resumen

Se construye de abajo hacia arriba en el dominio (TDD puro) y después por rebanadas verticales: cada funcionalidad atraviesa datos → servicios → web en su propio commit, con tests verdes.

## Decisiones tomadas al aprobar la spec

Las preguntas abiertas no se contestaron explícitamente, así que sigo las propuestas por defecto:

- **Base**: SQLite en local y en tests rápidos; Postgres en CI (service container) y en producción. En esta máquina no hay Docker, lo que confirma la decisión. ADR-0002.
- **Cuentas**: en la v1, como última funcionalidad; se recortan si algo se complica.
- **Permisos**: cualquier miembro edita y borra, todo queda en el historial.
- **Repo**: `git init` local; se sube a GitHub en la tarea de deploy.
- **PDF**: `fpdf2` (Python puro) en lugar de WeasyPrint, que necesita GTK/Pango y no instala en Windows ni en hostings sin `apt`. ADR-0006.

## Riesgos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| CSP estricta vs HTMX | Medio | HTMX con `allowEval=false`, `includeIndicatorStyles=false`; nada de `hx-on`; JS propio en archivos. |
| Diferencias SQLite/Postgres | Medio | Tests de integración en las dos en CI; sin SQL crudo. |
| API de cotización caída o cambiada | Bajo | Caché en base + carga manual; tests con `httpx.MockTransport`. |
| Hosting gratis cambió condiciones | Medio | Verificar en documentación oficial en la tarea de deploy. |
| Lighthouse en hosting que duerme | Bajo | Medir en local con build de producción; pantalla de "despertando" aparte. |
