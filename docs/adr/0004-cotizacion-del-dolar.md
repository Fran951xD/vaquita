# ADR-0004: Cotización del dólar guardada en cada gasto

Estado: aceptada · 2026-11-19

## Contexto

En Argentina un viaje mezcla pesos y dólares, y hay varios dólares (oficial, blue, MEP, tarjeta). Si los saldos se recalcularan con la cotización de hoy, cambiarían solos cada vez que se mueve el dólar.

## Decisión

- Cada gasto guarda el monto original, su moneda, la cotización usada (`Decimal`) y el tipo de dólar. El monto en la moneda del grupo se calcula una vez y queda fijo.
- La cotización se precarga en el formulario y se puede editar a mano:
  - del día de hoy, desde `dolarapi.com` (`/v1/dolares/{casa}`), con caché de una hora;
  - de días anteriores, desde `argentinadatos.com` (`/v1/cotizaciones/dolares/{casa}/{AAAA/MM/DD}`), que no cambian y se guardan para siempre.
  - El MEP se pide como `bolsa`. Ambas APIs se verificaron vigentes el 2026-11-19.
- Si las dos fallan, se usa la última cotización conocida y se avisa la fecha. Si no hay ninguna, la persona la escribe.
- Los tests usan `httpx.MockTransport`: nunca salen a internet.

## Consecuencias

- Los saldos son estables y auditables ("US$ 180 al blue de $ 1.640").
- Dependemos de APIs comunitarias sin SLA; por eso la caché y la carga manual.
