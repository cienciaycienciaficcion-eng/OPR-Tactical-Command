# OPR Tactical Command API — cuentas por invitación

## Requisitos nuevos de producción

Configurar en Render:
- `DATABASE_URL`: URL interna/externa de una base PostgreSQL de Render.
- `ADMIN_API_TOKEN`: secreto aleatorio largo para emitir invitaciones desde el endpoint administrativo.
- Mantener `GITHUB_APP_ID`, `GITHUB_CLIENT_ID`, `GITHUB_APP_PRIVATE_KEY`, `APP_SESSION_SECRET`, `GITHUB_OWNER` y `GITHUB_REPO`.

**No despliegues el nuevo backend hasta haber creado PostgreSQL y configurado ambas variables nuevas.** Las tablas se crean al arrancar. `APP_SESSION_SECRET` debe ser un secreto aleatorio y nunca debe publicarse.

## Flujo de registro

1. Un administrador emite una invitación con `POST /admin/invitations`, enviando `Authorization: Bearer <ADMIN_API_TOKEN>` y, por ejemplo, `{"expires_in_hours":168,"max_uses":1,"note":"Liga"}`.
2. Se entrega el código de invitación al jugador por un canal privado. Se guarda únicamente un hash del código en PostgreSQL.
3. La app inicia `POST /auth/device/start` y abre la URL de GitHub para que el usuario autorice Device Flow.
4. Durante `POST /auth/device/poll`, la app envía `{"device_code":"...","invite_code":"OPR-..."}`. Una cuenta nueva sin invitación no recibe sesión. La invitación se valida y consume una sola vez (o hasta `max_uses`), y se crea el perfil.
5. `GET /api/me` devuelve el perfil y `PATCH /api/me` cambia el nombre visible.
6. Las sesiones expiran a las 12 horas.

## Ejércitos y privacidad

- `POST /api/armies` guarda los datos privados en PostgreSQL; **no** los publica en GitHub.
- `GET /api/armies` lista los ejércitos del usuario autenticado.
- `GET /api/armies/{id}` permite ver el propio ejército; las copias compartidas también son consultables por usuarios autenticados.
- `PATCH /api/armies/{id}/sharing` con `{"shared":true}` publica una copia en `ejercitos-compartidos/` del repositorio central. Ese repositorio debe considerarse público: la acción hace que los datos sean públicamente visibles.
- Con `{"shared":false}` se intenta borrar la copia actual del repositorio y se vuelve a marcar privada en PostgreSQL. No se puede garantizar la eliminación de copias, forks, cachés o clones ya descargados.
- `GET /api/armies/shared` lista los ejércitos compartidos.

## Endpoints

- `GET /health`, `GET /health/database`, `GET /api/config`
- `POST /auth/device/start`
- `POST /auth/device/poll`
- `POST /admin/invitations`
- `GET /api/me`, `PATCH /api/me`
- `POST /api/armies`, `GET /api/armies`, `GET /api/armies/{army_id}`
- `PATCH /api/armies/{army_id}/sharing`
- `GET /api/armies/shared`
- `POST /api/battles` (mantiene la escritura de informes de batalla en el repositorio central)

## Nota sobre la app móvil

El ZIP de repositorio recibido contiene configuración Expo y backend, pero no contiene `app/`, `src/` ni componentes de interfaz de la app. Por tanto, este paquete actualiza el backend y su documentación, pero no puede integrar todavía las pantallas móviles de invitación, edición de perfil o compartir ejército. La app debe enviar `invite_code` en el cuerpo de `POST /auth/device/poll` para completar el alta de usuarios nuevos.
