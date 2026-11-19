# Plan de diseño — Vaquita

> Borrador para revisión, antes de escribir una línea de CSS.

## La idea

De día, **la libreta del almacén**: el cuaderno donde el almacenero anotaba "Juan debe $ 3.200" con birome azul y lo tachaba cuando le pagaban. De noche (modo oscuro), **el pizarrón del bodegón**: el mismo contenido escrito con tiza sobre verde oscuro.

La libreta no es decoración de toda la app. Aparece en **un solo lugar**, y ahí se gasta toda la audacia.

## El elemento memorable: la página de saldos

Saldos y "cómo saldar" se ven como **una hoja de libreta**: renglones finos, el margen rojo a la izquierda, y cada persona en su renglón con el monto alineado a la derecha en cifras tabulares.

```
 │
 │ Sofi        le deben   + $ 31.240,00
 │ Juan        debe       − $ 12.800,50
 │ Caro        debe       −  $ 9.100,00
 │ Tomi        le deben   +  $ 2.660,50
 │ Mati        está en cero   $ 0,00
 │──────────────────────────────────────
 │ Para quedar a mano
 │
 │ Juan  le pasa a  Sofi     $ 12.800,50
 │   alias sofi.mp  [Copiar]  [WhatsApp]  [Ya se lo pasé]
 │ Caro  le pasa a  Sofi      $ 9.100,00
 │   ...
```

Cuando alguien aprieta **"Ya se lo pasé"**, el renglón se **tacha con un trazo de birome** que se dibuja de izquierda a derecha (un `<path>` SVG con `stroke-dashoffset`, ~350 ms) y queda tachado, como en la libreta del almacén. Es **la única animación de la app** que no responde a otra cosa. Con `prefers-reduced-motion`, el tachado aparece sin animación.

Por qué este y no otro: es el momento en que la app cumple su promesa (quedar a mano), y el gesto de tachar es exactamente lo que se hacía en la libreta de verdad.

## Color

Día — libreta:

| Nombre | Hex | Uso |
|---|---|---|
| Hoja | `#F4F6F3` | fondo general (blanco frío, levemente verdoso; no crema) |
| Renglón | `#C9D3DC` | renglones de la libreta, bordes de campos |
| Birome | `#1F3A93` | color de marca: botones primarios, links, el tachado, foco |
| Margen | `#C0392B` | la línea del margen; también "debe" (siempre junto al signo − y la palabra) |
| Monte | `#2E6B3F` | "le deben" (siempre junto al signo + y la palabra) |
| Grafito | `#22262A` | texto |

Noche — pizarrón (no es un invertido; es otro material):

| Nombre | Hex | Uso |
|---|---|---|
| Pizarrón | `#1E2B27` | fondo |
| Marco | `#2C3B36` | superficies elevadas (formularios, hoja de carga) |
| Tiza | `#E8ECE6` | texto |
| Tiza azul | `#9DB6FF` | marca, foco, tachado |
| Tiza roja | `#FF9B8F` | "debe" |
| Tiza verde | `#9FD8A8` | "le deben" |

Todos los pares texto/fondo se verifican ≥ 4.5:1 (≥ 3:1 para bordes de controles y foco). Nunca se comunica deuda solo con color: signo, palabra y color van juntos.

## Tipografía

Dos familias, ambas de fundiciones argentinas, servidas localmente en `woff2` con subconjunto latino:

- **Archivo** (Omnibus-Type, Buenos Aires) — interfaz, formularios y **todos los montos**. Variable con eje de ancho: los montos usan `font-variant-numeric: tabular-nums` y un ancho apenas condensado (`wdth 92`) para que entren cifras largas en un celular sin achicar el cuerpo.
- **Bitter** (Huerta Tipográfica) — slab serif, solo para el nombre del grupo, los títulos de pantalla y el encabezado de la libreta. Tiene algo de máquina de escribir y de cuaderno, sin caer en letra "manuscrita".

A verificar en la primera tarea de UI: que el corte de Archivo que bajemos tenga `tnum` real. Plan B: Encode Sans (Impallari, también argentina).

Escala (base 17 px en celular, 18 px en escritorio, razón 1,25):

| Paso | Tamaño | Uso |
|---|---|---|
| −1 | 0,8 rem | ayudas, fechas |
| 0 | 1 rem | cuerpo, renglones de la libreta |
| 1 | 1,25 rem | montos de la lista de gastos |
| 2 | 1,56 rem | títulos de pantalla (Bitter) |
| 3 | 2,44 rem | el total del grupo, el monto mientras lo tipeás |

Sentence case en todo. Sin etiquetas en mayúsculas.

## Layout

Pensado para una mano: lo importante abajo, al alcance del pulgar.

Celular — pantalla del grupo:

```
┌──────────────────────────────┐
│ 🏔 Viaje a Bariloche    [⋯]  │  Bitter, nombre del grupo
│ Gastaron $ 1.284.500 entre 5 │
├──────────────────────────────┤
│ Gastos   Saldos   Resumen    │  tabs (subrayado birome en la activa)
├──────────────────────────────┤
│ Hoy                          │
│ Asado en la cabaña           │
│ pagó Sofi · entre 5   48.000 │  lista densa con separadores finos,
│ Nafta ida                    │  sin tarjetas
│ pagó Juan · entre 4   62.300 │
│ Ayer                         │
│ Cerro Catedral (US$ 180)     │
│ pagó Caro · entre 5  216.000 │
│                              │
├──────────────────────────────┤
│ [   + Cargar un gasto      ] │  barra fija abajo, botón ancho
└──────────────────────────────┘
```

Celular — cargar gasto (hoja que sube desde abajo, sin recargar con HTMX):

```
┌──────────────────────────────┐
│ ¿Cuánto fue?                 │
│ $ 48.000_                    │  teclado numérico, monto grande
│ ¿En qué?  [Asado          ]  │
│ Pagaste vos · entre todos ▸  │  una línea; tocás para cambiar
│ [        Guardar           ] │
└──────────────────────────────┘
```

Lo avanzado (varios pagadores, dividir distinto, dólares, fecha, categoría) vive detrás de esa línea "Pagaste vos · entre todos". El camino rápido es monto → concepto → Guardar.

Escritorio (≥ 900 px): dos columnas. Izquierda la lista de gastos (máx. ~40 rem); derecha la libreta de saldos fija mientras scrolleás. El formulario de carga queda arriba de la lista, siempre abierto en forma compacta.

```
┌───────────────────────────────────────────────────────┐
│ 🏔 Viaje a Bariloche                     Invitar  ⋯   │
├──────────────────────────────┬────────────────────────┤
│ [$ ____ ] [concepto ] [Guardar]│ │ Sofi  le deben +31.240│
│ Gastos · Resumen               │ │ Juan  debe     −12.800│
│ lista…                         │ │ … libreta …           │
└──────────────────────────────┴────────────────────────┘
```

Alineación: texto a la izquierda, montos a la derecha y alineados por la coma decimal (cifras tabulares + mismo número de decimales). Nada centrado salvo estados vacíos.

Radios: 6 px en campos y botones, 0 en la libreta (es papel). Sombras: solo en la hoja de carga del celular, porque está realmente encima de algo.

## Portada

Sin hero de marketing. Arriba, una frase que dice qué hace: **"Anotá quién puso qué. Vaquita te dice quién le pasa cuánto a quién."** Debajo, dos botones: **Crear un grupo** y **Ver un ejemplo**. Y abajo, una hoja de libreta real (el mismo componente de saldos, con datos fijos de un asado) que muestra el resultado antes de que lo pidas. Si el navegador recuerda grupos, aparecen primero: "Tus grupos".

## Textos

Voseo, directo, diciendo qué hacer:

- Vacío: "Todavía no hay gastos. Cargá el primero: ¿quién pagó qué?"
- Todos a mano: "Están todos a mano. No hay nada para pasar."
- Error de porcentajes: "Los porcentajes suman 90 %. Faltan 10 % para llegar a 100."
- Link revocado: "Este link ya no sirve. Pedile uno nuevo a alguien del grupo."
- Despertando (hosting gratis): "Estamos abriendo la libreta. Tarda unos segundos la primera vez."
- Confirmación de borrado: "¿Borrar «Nafta ida»? Queda en el historial."

## Principios

1. **Una sola audacia**: la libreta de saldos y su tachado. El resto es una interfaz callada.
2. **Los números mandan**: cifras tabulares, alineadas, con signo y palabra. Si un monto se ve mal, está mal diseñado.
3. **Pulgar primero**: la acción principal siempre abajo y ancha; objetivos táctiles de 44 px como mínimo.
4. **Listas, no tarjetas**: la información es tabular, se muestra como renglones.
5. **Movimiento solo como respuesta**: la hoja que sube, el tachado. Nada aparece "deslizándose" solo.
6. **Íconos casi cero**: el emoji del grupo y poco más. Palabras antes que pictogramas.

## Revisión contra el brief y contra los defaults

Lo que descarté y por qué:

- **Ticket de bar/comanda con tipografía mono** — fue mi primera idea. La descarté: el recibo térmico con fuente monoespaciada es justamente uno de los "looks" que se repiten en apps generadas, y la mono empeora la lectura de nombres.
- **Letra manuscrita para la libreta** — queda de cotillón y es ilegible en montos. La libreta se evoca con la estructura (renglones, margen, tachado), no con una fuente "a mano".
- **Fondo crema** — la libreta pedía papel cálido, pero crema + serif es uno de los clichés que pediste evitar. Lo cambié a un blanco frío verdoso, más cercano al papel de cuaderno escolar.
- **Rojo/verde como semáforo de deudas** — se mantienen porque son el código natural de "debe / le deben", pero nunca solos: siempre con signo y palabra, y con tonos chequeados para daltonismo (rojo ladrillo y verde monte, separados también en luminosidad).
- **Modo oscuro negro + acento brillante** — reemplazado por el pizarrón verde con tiza, que sale del mismo mundo.
- **Grilla de tarjetas para gastos** — reemplazada por lista de renglones con separadores finos.

Chequeo de lo prohibido: sin degradados violetas, sin glassmorphism, sin etiquetas en mayúsculas, sin "→" en botones, sin 01/02/03, sin animaciones de entrada por sección, sin frases de marketing.
