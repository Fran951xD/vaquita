# Guía de despliegue en Render, gratis

Planes verificados en la documentación oficial el 19 de noviembre de 2026:

- **Render, web service Free** ([render.com/docs/free](https://render.com/docs/free)): 750 horas por mes, 512 MB, se duerme a los 15 minutos sin tráfico y tarda cerca de un minuto en despertar. Sin disco persistente: por eso la base va aparte.
- **Neon, plan Free** ([neon.com/pricing](https://neon.com/pricing)): permanente, sin tarjeta, 1 GB por proyecto y 100 horas de cómputo por mes. Se suspende a los 5 minutos y despierta en milisegundos.
- **Render Postgres Free**: 1 GB, **vence a los 30 días** (más 14 de gracia) y después se borra.

El `render.yaml` crea la app y una base de Render conectadas solas: nadie copia la contraseña de la base a mano. Para una demo que dure más de un mes, pasá la base a Neon (sección 6).

Los planes cambian. Si algo de esto ya no es así, revisá esas dos páginas antes de seguir.

## 1. Subir el código a GitHub

```bash
git remote add origin https://github.com/Fran951xD/vaquita.git
git push -u origin main
```

GitHub Actions corre lint, tipos, tests (SQLite y Postgres), cobertura y e2e en cada push. Fijate que quede en verde en la pestaña **Actions**.

## 2. Crear la app y la base en Render

1. Entrá a [dashboard.render.com](https://dashboard.render.com) con tu cuenta de GitHub.
2. **New → Blueprint** y elegí el repo `vaquita`. Render lee `render.yaml`:
   - instala con `uv`, aplica las migraciones y arranca `uvicorn`;
   - crea la base `vaquita-db` y le pasa la conexión a la app (`DATABASE_URL`);
   - genera solo `VAQUITA_SECRET_KEY`;
   - pone `VAQUITA_ENTORNO=produccion` (cookies `Secure` y HSTS).
3. **Apply**. El primer deploy tarda unos minutos. Cuando termine, abrí `https://vaquita-XXXX.onrender.com/salud`: tiene que responder `{"estado":"ok"}`.
Probá la portada y **Ver un ejemplo**.

Si preferís no usar Blueprint: **New → Web Service**, runtime Python, plan Free, y copiá a mano `buildCommand`, `startCommand`, `healthCheckPath` y las variables de `render.yaml`. Para `VAQUITA_SECRET_KEY` generá una con:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

## 3. Página de espera para el portfolio

La app gratis se duerme. Para que quien abra el link vea algo prolijo mientras despierta, publicá `despertando/` en GitHub Pages:

1. En `despertando/index.html`, cambiá `const APP = "https://vaquita-k36x.onrender.com"` por la URL real de tu app.
2. En GitHub: **Settings → Pages → Build and deployment → Deploy from a branch**, rama `main`, carpeta `/ (root)`. Pages publica la carpeta raíz, así que la página queda en `https://Fran951xD.github.io/vaquita/despertando/`.
   - Si querés que esté en la raíz de Pages, creá una rama `gh-pages` que solo tenga ese `index.html` y publicá esa rama.
3. Poné ese link en el README y en tu CV. La página consulta `/salud` cada 3 segundos y te lleva a la app apenas responde.

## 4. Después del deploy

- **Lighthouse**: en Chrome, DevTools → Lighthouse → Mobile, sobre la portada y sobre un grupo de ejemplo (con la app ya despierta).
- **Logs**: Render → tu servicio → Logs. Los tokens de invitación aparecen tapados (`/i/***`).
- **Actualizar**: cada push a `main` despliega solo. Las migraciones nuevas se aplican al arrancar.
- **Dominio propio** (opcional): Render → Settings → Custom Domains.

## 5. Problemas comunes

| Síntoma | Causa probable |
|---|---|
| El deploy falla en `alembic upgrade head` | `DATABASE_URL` mal copiada o sin `sslmode=require` |
| "Falta VAQUITA_SECRET_KEY en producción" | La variable no está cargada en Render |
| Los links de invitación salen con `http://` | Falta `--proxy-headers` en el comando de inicio |
| Todo da 404 después de cambiar la clave | Cambiar `VAQUITA_SECRET_KEY` invalida sesiones y links: es esperado |
| La app no arranca después de un mes | Venció la base gratis de Render: pasala a Neon (sección 6) |

## 6. Pasar la base a Neon (permanente)

1. En [console.neon.tech](https://console.neon.tech) creá un proyecto `vaquita` en São Paulo y copiá la cadena de conexión.
2. En Render → servicio `vaquita` → **Environment**, reemplazá `DATABASE_URL` por la cadena de Neon y guardá. Render redespliega y las migraciones crean las tablas.
3. Si querés conservar los datos, antes copiá la base con `pg_dump` desde Render y `psql` hacia Neon.
4. Borrá `databases:` y el `fromDatabase` del `render.yaml` para que el Blueprint no la vuelva a crear.
