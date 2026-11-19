# ADR-0006: Interfaz renderizada en el servidor con Jinja2 y HTMX

Estado: aceptada · 2026-11-19

## Contexto

El proyecto tiene que mostrar que es Python. Una SPA en React movería la mitad de la lógica a JavaScript y duplicaría validaciones.

## Decisión

- Las pantallas son plantillas Jinja2. HTMX (servido localmente, versión fija) hace las partes dinámicas: guardar un gasto sin recargar devuelve el formulario limpio y actualiza la lista y la libreta con swaps fuera de banda; "Ya se lo pasé" reemplaza solo la libreta.
- Todo funciona sin JavaScript: la hoja de carga es un `<dialog>` que, sin JS, es un link a una página con el mismo formulario.
- El JavaScript propio (`vaquita.js`, unas 80 líneas) solo agrega comodidades: copiar el alias, abrir la hoja, mostrar los campos de la forma de dividir elegida.
- Los gráficos son SVG generados en el servidor: sin librerías.
- El PDF se arma con `fpdf2` (Python puro). WeasyPrint necesita GTK/Pango, que no se instala en Windows ni en un hosting sin `apt`.

## Consecuencias

- Una sola fuente de verdad para validar: el servidor (Pydantic + dominio).
- Páginas livianas: Lighthouse móvil 99 a 100 en performance sin bundler.
- Algunas interacciones muy ricas (arrastrar, edición en línea) serían más trabajo que en una SPA; no hacen falta en la v1.
