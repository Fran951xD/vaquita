# ADR-0005: Acceso sin cuenta con cookie firmada y link de invitación

Estado: aceptada · 2026-11-19

## Contexto

Pedirle a cinco amigos que se creen una cuenta para anotar un asado es perder a cuatro. Pero los datos de un grupo (y sobre todo los alias y CVU) no pueden quedar a la vista de cualquiera.

## Decisión

- **Invitación**: el link es `/i/{token}`, con `token = HMAC-SHA256(clave, id_de_la_invitación)` (256 bits). En la base solo queda el SHA-256 del token, para buscarlo. Como el token se deriva, cualquier miembro puede volver a ver el link sin que esté guardado en claro. Revocar = crear una invitación nueva.
- **Identidad**: al elegir tu nombre, el navegador guarda `{grupo: miembro}` en la cookie de sesión de Starlette, firmada con `itsdangerous`, `HttpOnly`, `SameSite=Lax` y `Secure` en producción.
- **Autorización**: toda ruta de grupo pasa por la dependencia `en_grupo`, que exige el grupo en la cookie y carga el miembro solo dentro de ese grupo. Cualquier id de otro grupo da 404. Hay tests que lo intentan por todas las rutas.
- **CSRF**: token sincronizado en la sesión; formularios con campo oculto y HTMX con la cabecera `X-CSRF-Token`.
- **CSP estricta** sin `unsafe-inline`: nada de estilos ni scripts en línea; HTMX configurado sin `eval`.
- **Rate limiting** en memoria (ventana deslizante por IP) en crear grupo, ejemplo, entrar por link y login. Alcanza para una sola instancia, que es lo que da el plan gratis; con más instancias habría que pasarlo a Redis o a la base.
- **Cuentas opcionales** con Argon2id; mismo mensaje y mismo tiempo si el email no existe o la contraseña es incorrecta.
- **Logs**: el token de los links se tapa en los logs de acceso.

## Consecuencias

- Entrar a un grupo lleva dos toques y cero formularios de registro.
- Quien tenga el link puede entrar y elegir cualquier nombre: es el mismo modelo de confianza que una planilla compartida. Por eso el link se puede cambiar y todo queda en el historial.
- Cambiar `VAQUITA_SECRET_KEY` invalida los links y las sesiones.
