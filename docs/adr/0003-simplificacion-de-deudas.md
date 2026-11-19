# ADR-0003: Simplificación de deudas con un algoritmo voraz

Estado: aceptada · 2026-11-19

## Contexto

Después de un viaje con 30 gastos, "quién le debe a quién" puede ser una maraña. Lo que la gente quiere es la menor cantidad de transferencias para quedar a mano.

Encontrar el mínimo exacto es NP-difícil: equivale a partir a las personas en la mayor cantidad posible de subgrupos cuyos saldos sumen cero (el mínimo es `n − cantidad de subgrupos`).

## Decisión

`vaquita/dominio/deudas.py` es un módulo puro (sin base, sin framework). Calcula:

1. **Saldos**: lo que cada uno puso, menos lo que le tocaba, más los pagos que hizo, menos los que recibió. La suma da cero siempre.
2. **Simplificar** (por defecto): en cada vuelta, el que más debe le paga al que más le deben, por el menor de los dos montos. Los empates se resuelven por el orden fijo del grupo, así el resultado es determinista.
3. **No simplificar** (opcional por grupo): cada uno le paga a quien le pagó. Se arma la deuda de cada par a partir de los gastos (si pagaron varios, la parte de cada persona se cubre en orden con lo que puso cada pagador, sin perder centavos) y se compensa solo dentro de cada par.

## Por qué voraz y no el óptimo

- Cada vuelta deja en cero al menos a una persona, así que **nunca hay más de `n − 1` transferencias**. Está probado con Hypothesis.
- Es `O(n²)` y se explica en una línea.
- No siempre es óptimo. Contraejemplo (en miles de pesos): A +2, B +4, C −5, D −4, E +3. El voraz hace 4 transferencias (C→B 4, D→E 3, C→A 1, D→A 1); el óptimo hace 3, porque {B, D} suman cero: D→B 4, C→E 3, C→A 2.
- Para grupos de amigos (5 a 10 personas) la diferencia rara vez pasa de una transferencia. Una búsqueda exacta por subconjuntos (`O(3ⁿ)`) queda para la v2.

## Invariantes con tests de propiedades

- La suma de los saldos es cero.
- Aplicar las transferencias sugeridas (simplificadas o no) deja a todos en cero.
- Las transferencias simplificadas nunca son más que miembros − 1, y siempre son positivas entre personas distintas.
- El resultado es determinista.
