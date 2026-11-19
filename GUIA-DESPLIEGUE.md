# Guía de despliegue: Render + Neon, gratis

Planes verificados en la documentación oficial el 19 de noviembre de 2026:

- **Render, web service Free** ([render.com/docs/free](https://render.com/docs/free)): 750 horas por mes, 512 MB, se duerme a los 15 minutos sin tráfico y tarda cerca de un minuto en despertar. Sin disco persistente: por eso la base va aparte.
- **Neon, plan Free** ([neon.com/pricing](https://neon.com/pricing)): permanente, sin tarjeta, 1 GB por proyecto y 100 horas de cómputo por mes. Se suspende a los 5 minutos y despierta en milisegundos.
- No uso Render Postgres porque la base gratis vence a los 30 días y después se borra.

Los planes cambian. Si algo de esto ya no es así, revisá esas dos páginas antes de seguir.

## 1. Subir el código a GitHub

```bash
git remote add origin https://github.com/TU-USUARIO/vaquita.git
git push -u origin main
```

GitHub Actions corre lint, tipos, tests (SQLite y Postgres), cobertura y e2e en cada push. Fijate que quede en verde en la pestaña **Actions**.

## 2. Crear la base en Neon

1. Entrá a [console.neon.tech](https://console.neon.tech) y creá una cuenta (podés usar la de GitHub).
2. **New project**: nombre `vaquita`, Postgres 17, región **AWS São Paulo (sa-east-1)**, la más cercana a Argentina.
3. En **Connection details** copiá la cadena de conexión. Tiene esta forma:
   `postgresql://usuario:clave@ep-xxxx.sa-east-1.aws.neon.tech/neondb?sslmode=require`
   No hace falta cambiarle nada: la app la adapta al driver `psycopg`.

## 3. Crear la app en Render

1. Entrá a [dashboard.render.com](https://dashboard.render.com) con tu cuenta de GitHub.
2. **New → Blueprint** y elegí el repo `vaquita`. Render lee `render.yaml`:
   - instala con `uv`, aplica las migraciones y arranca `uvicorn`;
   - genera solo `VAQUITA_SECRET_KEY`;
   - pone `VAQUITA_ENTORNO=produccion` (cookies `Secure` y HSTS).
3. Te va a pedir `DATABASE_URL`: pegá la cadena de Neon del paso 2.
4. **Apply**. El primer deploy tarda unos minutos. Cuando termine, abrí `https://vaquita-XXXX.onrender.com/salud`: tiene que responder `{"estado":"ok"}`.
5. Probá la portada y **Ver un ejemplo**.

Si preferís no usar Blueprint: **New → Web Service**, runtime Python, plan Free, y copiá a mano `buildCommand`, `startCommand`, `healthCheckPath` y las variables de `render.yaml`. Para `VAQUITA_SECRET_KEY` generá una con:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

## 4. Página de espera para el portfolio

La app gratis se duerme. Para que quien abra el link vea algo prolijo mientras despierta, publicá `despertando/` en GitHub Pages:

1. En `despertando/index.html`, cambiá `const APP = "https://vaquita.onrender.com"` por la URL real de tu app.
2. En GitHub: **Settings → Pages → Build and deployment → Deploy from a branch**, rama `main`, carpeta `/ (root)`. Pages publica la carpeta raíz, así que la página queda en `https://TU-USUARIO.github.io/vaquita/despertando/`.
   - Si querés que esté en la raíz de Pages, creá una rama `gh-pages` que solo tenga ese `index.html` y publicá esa rama.
3. Poné ese link en el README y en tu CV. La página consulta `/salud` cada 3 segundos y te lleva a la app apenas responde.

## 5. Después del deploy

- **Lighthouse**: en Chrome, DevTools → Lighthouse → Mobile, sobre la portada y sobre un grupo de ejemplo (con la app ya despierta).
- **Logs**: Render → tu servicio → Logs. Los tokens de invitación aparecen tapados (`/i/***`).
- **Actualizar**: cada push a `main` despliega solo. Las migraciones nuevas se aplican al arrancar.
- **Dominio propio** (opcional): Render → Settings → Custom Domains.

## Problemas comunes

| Síntoma | Causa probable |
|---|---|
| El deploy falla en `alembic upgrade head` | `DATABASE_URL` mal copiada o sin `sslmode=require` |
| "Falta VAQUITA_SECRET_KEY en producción" | La variable no está cargada en Render |
| Los links de invitación salen con `http://` | Falta `--proxy-headers` en el comando de inicio |
| Todo da 404 después de cambiar la clave | Cambiar `VAQUITA_SECRET_KEY` invalida sesiones y links: es esperado |
| Neon dice que se pasó de horas | Llegaste a las 100 horas del mes; vuelve el mes siguiente |
