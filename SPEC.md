# Spec: Vaquita — V1

> Estado: **borrador para revisión**. No se escribe código hasta el OK.

## Supuestos que estoy tomando

1. App web responsive; no hay app nativa ni PWA instalable en la v1.
2. Una sola instancia de servidor (hosting gratis). Nada de colas ni workers: las tareas periódicas (gastos fijos, borrado de demos) corren **perezosamente** al entrar a un grupo y al arrancar la app, de forma idempotente.
3. Sin cuenta, la identidad es "soy este miembro en este grupo", guardada en una cookie firmada por navegador. No hay permisos distintos entre miembros: cualquiera del grupo puede cargar, editar y borrar (como en la libreta real), y todo queda en el historial.
4. Un grupo tiene una moneda principal fija (ARS o USD); no se puede cambiar después de cargar el primer gasto.
5. Navegadores modernos (últimas 2 versiones de Chrome, Safari iOS, Firefox).
6. Montos máximos por gasto: $ 999.999.999,99 (cabe holgado en `BIGINT` de centavos).

Corregime cualquiera de estos antes de seguir.

## Objetivo

Que un grupo de amigos anote quién puso cuánto (el asado, el viaje, el alquiler del depto) y al final sepa **quién le pasa cuánto a quién con la menor cantidad razonable de transferencias**, sin crear cuenta y desde el celular, en la mesa.

Para quién:
- **El que organiza**: crea el grupo, comparte el link por WhatsApp.
- **Los demás**: entran por el link, eligen su nombre, cargan gastos en menos de 10 segundos.
- **Quien revisa el portfolio**: aprieta "Ver un ejemplo" y en un clic tiene un viaje a Bariloche con 30 gastos para explorar.

Éxito = el flujo completo (crear → invitar → cargar → saldar → exportar) funciona en celular y escritorio, la plata nunca pierde ni inventa un centavo, y el código se lee como un proyecto Python serio.

## Mapa de módulos y orden de construcción

Una sola spec (es un producto chico), pero con límites claros entre capas:

| Módulo | Responsabilidad | Depende de |
|---|---|---|
| `dominio` | Dinero (centavos), división, redondeo, saldos, simplificación de deudas, conversión de moneda. Puro: sin I/O, sin framework, sin base. | — |
| `datos` | Modelos SQLAlchemy 2.0 tipados, repositorios, migraciones Alembic. | `dominio` (tipos) |
| `servicios` | Casos de uso: crear grupo, cargar gasto, saldar, historial, cotización, gastos fijos, demo, export. Transacciones. | `dominio`, `datos` |
| `web` | Rutas FastAPI, plantillas Jinja2, parciales HTMX, seguridad (CSRF, cabeceras, rate limit). | `servicios` |

Orden: `dominio` (TDD) → `datos` → `servicios` → `web` por rebanadas verticales (cada funcionalidad atraviesa las capas en su propio commit).

## Stack

| Pieza | Elección |
|---|---|
| Lenguaje | Python 3.12+ |
| Web | FastAPI + Jinja2 + HTMX (servido localmente, versión fija). JS propio mínimo, sin frameworks. |
| Validación | Pydantic v2 |
| Base | PostgreSQL en producción y CI. SQLite para el arranque local en 3 comandos. **Decisión en ADR-0002** (ver Preguntas abiertas). |
| ORM / migraciones | SQLAlchemy 2.0 (`Mapped[...]`), Alembic |
| Contraseñas | Argon2 (`argon2-cffi`) |
| Rate limiting | En memoria, propio y chico (una instancia sola); ADR justifica no usar Redis |
| PDF | `fpdf2` (Python puro, con las fuentes de la app embebidas). WeasyPrint descartado: necesita GTK/Pango (ADR-0006) |
| Excel | CSV nativo + `openpyxl` para `.xlsx` |
| Tests | pytest, pytest-cov, Hypothesis, Playwright (Python) + `axe-core` inyectado |
| Calidad | Ruff (lint + formato), mypy `--strict` sobre `dominio/` y `servicios/` |
| Gestor | `uv` |
| CI | GitHub Actions: ruff, mypy, pytest (SQLite y Postgres), cobertura, e2e |
| Deploy | Se elige y verifica contra documentación oficial en la tarea de deploy (candidatos: Render/Koyeb/Fly + Neon). Pantalla de "despertando" si duerme. |

## Comandos

```bash
uv sync                                   # instalar
uv run alembic upgrade head               # migrar
uv run fastapi dev vaquita/web/app.py     # levantar en http://localhost:8000

uv run pytest                             # unit + integración
uv run pytest --cov=vaquita --cov-report=term-missing
uv run pytest e2e/ --browser chromium     # Playwright
uv run ruff check . && uv run ruff format --check .
uv run mypy vaquita/dominio vaquita/servicios
```

## Estructura

```
vaquita/
  dominio/      dinero.py, division.py, saldos.py, deudas.py, cotizacion.py
  datos/        modelos.py, repositorios/, migraciones/ (Alembic)
  servicios/    grupos.py, gastos.py, pagos.py, saldar.py, historial.py,
                cotizaciones.py, fijos.py, demo.py, exportar.py, cuentas.py
  web/          app.py, rutas/, plantillas/, estaticos/ (css, js, fuentes, htmx),
                seguridad.py (csrf, cabeceras, rate limit, cookies)
tests/
  dominio/      unitarios + Hypothesis
  integracion/  rutas con base real, aislamiento entre grupos
e2e/            Playwright (celular 390×844 y escritorio 1280×800) + axe
docs/adr/       ADRs numerados
SPEC.md  DISENO.md  README.md  GUIA-DESPLIEGUE.md  LICENSE
```

## Modelo de datos

Todos los montos son **enteros en centavos** (`BIGINT`). Cotizaciones como `Decimal` guardado en texto/`NUMERIC(18,6)`. Nunca `float`.

```
Grupo         id (uuid), nombre, emoji, moneda (ARS|USD), tipo (viaje|depto|salida|otro),
              simplificar (bool), es_demo, creado_en, borrar_despues_de (demos)
Invitacion    id, grupo_id, token_hash (sha256 de 32 bytes de secrets), creada_en, revocada_en
Miembro       id (uuid), grupo_id, nombre, alias_cbu (nullable), cuenta_id (nullable), orden
Gasto         id (uuid), grupo_id, concepto, categoria, fecha,
              monto_original_centavos, moneda_original, cotizacion (Decimal|null),
              tipo_dolar (oficial|blue|mep|tarjeta|manual|null), monto_centavos (en moneda del grupo),
              forma_division (iguales|exactos|porcentajes|partes), gasto_fijo_id (nullable),
              creado_por, borrado_en (borrado lógico para el historial)
Aporte        gasto_id, miembro_id, centavos          -- quién pagó (uno o varios)
Parte         gasto_id, miembro_id, centavos, peso    -- a quién le corresponde; peso = %, partes o null
Pago          id, grupo_id, de_miembro, a_miembro, centavos, fecha, origen (manual|saldar)
GastoFijo     id, grupo_id, plantilla (concepto, monto, moneda, aportes, división),
              dia_del_mes, ultimo_generado (año-mes), activo
Evento        id, grupo_id, miembro_id, tipo, resumen_texto, datos_json, creado_en   -- historial
Cotizacion    fecha, tipo_dolar, compra, venta, fuente, obtenida_en              -- caché
Cuenta        id, email (único, normalizado), hash_password, creada_en
```

Invariantes en la base: `SUM(aporte) = monto_centavos = SUM(parte)` por gasto (verificado en servicio y con test); `centavos > 0`; `de_miembro ≠ a_miembro`.

## Reglas de dinero

- `Centavos` es un `int` con tipo propio (`NewType`). Conversión de texto del usuario (`"12.500,50"`) → centavos en un solo lugar, con `Decimal` y redondeo `ROUND_HALF_EVEN`; si trae más de 2 decimales, error de validación (no se redondea en silencio).
- **División**: se calcula la parte entera de cada uno y los centavos sobrantes se reparten de a uno siguiendo el **orden fijo del miembro** (`Miembro.orden`), empezando por quien tiene el mayor resto (método del mayor resto, desempate por orden). Determinista y `sum(partes) == total` siempre.
- **Conversión de moneda**: `monto_centavos = round_half_even(original × cotización)` una sola vez al guardar; la cotización queda en el gasto. Cambiar la cotización del día no altera gastos viejos.
- **Saldo** de cada miembro = aportes − partes + pagos hechos − pagos recibidos (signo: positivo = le deben; pagar una deuda acerca a cero).
- **Simplificación** (`dominio/deudas.py`): voraz, empareja al mayor deudor con el mayor acreedor hasta vaciar. Garantiza ≤ n−1 transferencias. No promete el mínimo exacto (problema NP-difícil); el ADR-0003 lo explica y muestra un contraejemplo.
- **No simplificar**: deudas por par (quién le debe a quién por lo que pagó cada uno), compensadas solo dentro de cada par.

### Invariantes con Hypothesis
1. La suma de todos los saldos de un grupo es 0.
2. Aplicar las transferencias sugeridas deja todos los saldos en 0.
3. `len(transferencias) ≤ miembros − 1` (con saldos no nulos).
4. Ninguna división pierde ni inventa un centavo, para las cuatro formas.
5. Determinismo: mismos datos → mismas partes y mismas transferencias.

## Funcionalidades y criterios de aceptación

### Grupos e invitaciones
- Crear grupo con nombre, emoji, moneda, tipo y los nombres de los primeros miembros. → queda en la cookie del navegador como "tus grupos".
- Link `/<token>` con token de 32 bytes (`secrets.token_urlsafe`); en base se guarda solo su hash. Se puede revocar y generar uno nuevo; el viejo devuelve una página "Este link ya no sirve, pedile uno nuevo a tu grupo".
- Al entrar: "¿Quién sos?" con la lista de miembros + "No estoy, agregarme".
- URLs internas usan UUID, nunca IDs secuenciales.

### Gastos
- Campos: monto, moneda, concepto, categoría (asado/comida, súper, transporte, alojamiento, salidas, servicios, alquiler, otros), fecha (hoy por defecto), quién pagó (uno o varios con montos), entre quiénes y cómo.
- Formas: iguales, montos exactos (deben sumar el total), porcentajes (deben sumar 100), partes (enteros ≥ 1).
- **Camino rápido < 10 s**: monto → concepto → Guardar. Defaults: pagaste vos, entre todos, partes iguales, moneda del grupo, hoy.
- Editar y borrar (lógico). Cada cambio genera un `Evento` legible: "Sofi cambió el asado de $ 45.000 a $ 48.000".
- Errores de validación en línea, en español, junto al campo.

### Pagos
- "Juan le pasó $ 8.500 a Sofi" como movimiento aparte; afecta saldos, aparece en la lista y en el historial.

### Gastos fijos
- Plantilla mensual con día del mes. Al abrir el grupo se generan los meses pendientes hasta hoy (idempotente: un gasto por plantilla por mes, con restricción única en base).

### Pesos y dólares
- Gasto en ARS o USD; si difiere de la moneda del grupo se elige tipo de dólar (oficial, blue, MEP, tarjeta) y se precarga la cotización del día de la fuente pública, editable a mano.
- Caché por (fecha, tipo) en base. Si la API falla: se usa la última conocida avisando la fecha, o se pide carga manual.
- Fuente (dolarapi.com / argentinadatos.com, que tiene históricos): **se verifica en la tarea correspondiente** cuál está vigente y cuál sirve para fechas pasadas.

### Saldos y saldar
- Saldo por persona: puso / le corresponde / resultado, con signo y palabra ("le deben", "debe"), no solo color.
- Lista de transferencias sugeridas (simplificadas o no, según el grupo).
- Cada miembro guarda alias/CVU; en "Saldar" se copia con un toque y hay botón de WhatsApp con el mensaje armado (`https://wa.me/?text=...`).
- "Ya se lo pasé" crea el `Pago` (origen `saldar`) y la deuda se tacha.

### Resumen
- Total del grupo, por persona, por categoría, en el tiempo (por semana o mes según el rango). SVG generado en el servidor, con `<title>`/`<desc>` y tabla equivalente para lectores de pantalla.
- Exportar CSV, XLSX y PDF (resumen de una o dos páginas, mismo lenguaje visual).

### Demo
- "Ver un ejemplo" crea "Viaje a Bariloche": 5 amigos, ~30 gastos en ARS y USD, varias formas de división, un pago, un gasto fijo. Se marca `es_demo`, se borra a las 6 h (limpieza perezosa). Rate limit propio.

### Cuentas (opcional, última en el orden)
- Email + contraseña (Argon2). Vincular miembros de grupos a la cuenta para verlos todos juntos. Sin recuperación por email en la v1 (no hay envío de correo gratis confiable; ver Deferred).

## Seguridad

- CSRF: token sincronizado por sesión en todo `POST/PUT/DELETE`, también en pedidos HTMX (cabecera).
- Cookies `HttpOnly`, `Secure` (en prod), `SameSite=Lax`, firmadas (`itsdangerous`).
- Cabeceras: CSP estricta sin `unsafe-inline` (HTMX configurado sin eval, sin estilos inline), HSTS, `X-Content-Type-Options`, `Referrer-Policy: no-referrer` (el token va en la URL), `Permissions-Policy`.
- Toda consulta filtra por `grupo_id` de la sesión; tests de integración intentan leer, editar y borrar gastos, pagos, miembros y alias de otro grupo y esperan 404.
- Rate limit: crear grupo, demo, login, entrar por link.
- Logs sin tokens, alias, CVU, emails ni montos asociados a nombres.

## Estrategia de tests

| Nivel | Qué | Dónde |
|---|---|---|
| Unitario + propiedades | todo `dominio/`, TDD estricto | `tests/dominio/` |
| Integración | servicios y rutas con base real (SQLite y Postgres en CI), aislamiento entre grupos, CSRF, rate limit | `tests/integracion/` |
| E2E | crear grupo, invitar, gastos de las 4 formas y en USD, saldar, exportar; celular y escritorio | `e2e/` |
| Accesibilidad | axe sin violaciones serias en portada, grupo, cargar gasto, saldos, saldar, resumen | `e2e/` |

Cobertura: `dominio/` ≥ 95 %, total ≥ 85 % (CI falla por debajo).

## Criterios de éxito

- [ ] Todos los tests verdes en CI; cobertura cumplida; ruff y mypy estricto limpios.
- [ ] Las 5 invariantes cubiertas con Hypothesis.
- [ ] Cargar un gasto por el camino rápido en el celular: ≤ 3 interacciones después de abrir el formulario.
- [ ] Lighthouse ≥ 90 en las 4 categorías en portada y pantalla de grupo (móvil).
- [ ] axe sin violaciones `serious`/`critical`; navegable entero con teclado; `prefers-reduced-motion` respetado.
- [ ] Ningún test de acceso cruzado entre grupos logra leer o modificar nada.
- [ ] Desplegada en un hosting gratis con la guía paso a paso probada.
- [ ] README de portfolio con capturas, demo, 3 comandos, ADRs y "Cómo lo construí".

## Límites

- **Siempre**: test primero en lógica de dinero; un commit por tarea con tests verdes; mensajes de commit en español; validar en el servidor.
- **Preguntar antes**: agregar dependencias fuera de este stack; cambiar el modelo de datos ya migrado; elegir el hosting final; cualquier cosa que publique o cree cuentas externas.
- **Nunca**: `float` para plata; IA dentro de la app; secretos en el repo; borrar un test que falla para pasar CI; CDN externos en producción.

## Fuera de alcance (v2)

- Recuperar contraseña por email — requiere servicio de correo.
- Fotos de tickets — almacenamiento de archivos.
- Más monedas además de ARS/USD.
- Notificaciones push o por email.
- PWA offline — complejidad de sincronización.
- Permisos por rol (admin del grupo).
- Simplificación óptima exacta (búsqueda por subconjuntos) — la voraz alcanza para grupos reales.
- Internacionalización.

## Preguntas abiertas

1. **Base local**: propongo Postgres en producción y CI, y SQLite solo para correrla en local sin Docker (los tests de integración corren contra las dos en CI). Alternativa más simple: Postgres en Docker para todo. ¿Cuál preferís?
2. **Cuentas**: ¿las dejamos en la v1 como la última tarea (y se recortan si el resto se complica) o las pasamos directo a v2?
3. **Permisos**: ¿te parece bien que cualquier miembro pueda editar/borrar cualquier gasto (con historial), o solo quien lo cargó?
4. **Repo**: ¿lo creo con `git init` acá y vos lo subís a GitHub, o ya tenés el repo `vaquita` clonado en alguna carpeta?
