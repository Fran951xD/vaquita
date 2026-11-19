# ADR-0007: Despliegue gratis en Render

Estado: aceptada · 2026-11-19 (planes verificados en la documentación oficial ese día)

## Opciones evaluadas

| Opción | App | Base | Problema |
|---|---|---|---|
| Render + Render Postgres | Gratis, duerme a los 15 min, ~1 min en despertar, 750 h/mes | Gratis pero **vence a los 30 días** y después se borra | La base no sirve para una demo permanente |
| Koyeb | Gratis, duerme a la hora sin tráfico | Postgres gratis de 5 h de cómputo, 1 GB | Pocas horas de base; una sola app gratis |
| **Render + Neon** | Igual que arriba | Gratis permanente, 1 GB, se suspende a los 5 min y despierta en milisegundos | La app tarda en despertar |

Fly.io ya no ofrece plan gratis para cuentas nuevas.

## Decisión

App en Render (plan `free`, `render.yaml` en el repo). Para el primer despliegue la base es el Postgres gratis de Render, declarado en el mismo Blueprint: la conexión se inyecta con `fromDatabase` y nadie copia credenciales a mano. Como vence a los 30 días, el destino es Neon (plan Free, permanente): pasarla es cambiar una variable (guía, sección 6). La organización de Neon disponible al desplegar estaba administrada por Vercel y no permitía crear proyectos desde Neon. Las tareas periódicas no usan cron: los gastos fijos se generan al abrir el grupo y los grupos de ejemplo vencidos se borran al crear uno nuevo.

Para el arranque en frío hay una página estática (`despertando/`, publicable en GitHub Pages) con la estética de la libreta que despierta la app y redirige apenas responde. Render además muestra su propia pantalla de carga.

## Consecuencias

- Costo cero, sin tarjeta.
- La primera visita después de un rato tarda cerca de un minuto: por eso el link del portfolio apunta a la página de espera.
- Una sola instancia: el rate limiting en memoria alcanza (ADR-0005).
