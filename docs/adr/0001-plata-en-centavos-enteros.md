# ADR-0001: La plata se guarda en centavos enteros

Estado: aceptada · 2026-11-19

## Contexto

Una app que divide gastos vive de sumas y restas de plata. Con `float`, `0.1 + 0.2 != 0.3`, y un saldo de `-0.0000001` que no es cero rompe la promesa de "quedaron todos a mano". Además, al dividir $ 10 entre tres alguien tiene que poner el centavo que sobra, y tiene que ser siempre el mismo.

## Decisión

- Todo monto es un `int` de centavos de la moneda indicada, con un tipo propio (`Centavos = NewType(...)`) en `vaquita/dominio/dinero.py`. En la base es `BIGINT`.
- El texto que tipea la persona (`"12.500,50"`) se convierte en un solo lugar, `parsear_monto`. Si trae más de dos decimales se rechaza con un mensaje: no se redondea en silencio.
- Las cotizaciones son `Decimal` (guardadas como texto en la base para que SQLite no las pase a `REAL`). Se aplican una sola vez, al guardar el gasto, con redondeo bancario (`ROUND_HALF_EVEN`).
- Al dividir se usa el método del mayor resto: cada uno recibe la parte entera y los centavos sobrantes van, de a uno, a quien tiene el mayor resto; si hay empate, a quien está antes en el orden fijo del grupo. La suma de las partes es exactamente el total.

## Consecuencias

- Las invariantes ("la suma de los saldos es cero", "ninguna división pierde un centavo") se pueden probar con Hypothesis sobre enteros, sin tolerancias.
- Mostrar un monto requiere formatearlo (`formatear`), pero eso pasa en un solo lugar.
- Excel recibe números (`Decimal / 100`), porque es lo que espera quien abre la planilla; la fuente de verdad sigue siendo el entero.
