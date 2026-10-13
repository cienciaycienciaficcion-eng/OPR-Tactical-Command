# OPR Tactical Command API

Backend inicial para autenticar usuarios con GitHub Device Flow y guardar ejércitos/reportes en el repositorio central usando una GitHub App installation token.

## Variables de entorno

- `GITHUB_APP_ID`: App ID público de GitHub App.
- `GITHUB_CLIENT_ID`: Client ID público de GitHub App; Device Flow debe estar habilitado en los ajustes de la app.
- `GITHUB_APP_PRIVATE_KEY`: contenido completo del `.pem`, guardado como secreto en el servicio de hosting. Nunca se añade al repositorio ni a la APK.
- `APP_SESSION_SECRET`: secreto aleatorio largo para firmar sesiones propias del backend.
- `GITHUB_OWNER`: `cienciaycienciaficcion-eng`.
- `GITHUB_REPO`: `OPR-Tactical-Command`.

## Endpoints

- `GET /health`
- `GET /api/config`
- `POST /auth/device/start` -> entrega el código de usuario y la URL de autorización.
- `POST /auth/device/poll` -> consulta la autorización; al finalizar entrega una sesión de la API (no devuelve el token OAuth de GitHub).
- `POST /api/armies` -> requiere `Authorization: Bearer <session_token>`; guarda `ejercitos/<login>/...json`.
- `POST /api/battles` -> requiere sesión; guarda un archivo de batalla en `batallas/<año>/...json`.

## Despliegue desde GitHub

El archivo `render.yaml` de la raíz del repositorio es un Blueprint para desplegar el servicio desde un repositorio conectado a Render. GitHub Actions no puede actuar como servidor HTTP permanente, por lo que hace falta un servicio web para que la APK pueda conectarse cuando quiera.

En Render, al crear el Blueprint, configurar `GITHUB_APP_ID=5300354`, el Client ID mostrado en GitHub y el contenido de la clave `.pem` en las variables secretas. No guardar la clave privada en GitHub ni en el ZIP de la APK.

## Importante: instalación y permisos

La GitHub App debe estar instalada en `cienciaycienciaficcion-eng/OPR-Tactical-Command` y tener `Contents: Read and write`. Device Flow debe estar habilitado. El usuario que inicia sesión no necesita ser colaborador: el backend escribe con el token de instalación de la App.

## Estado de esta entrega

Es una base inicial de backend. No desplegar a producción sin pruebas de autenticación, permisos, límites, control de abuso y concurrencia. Los reportes se guardan como archivos individuales; la actualización de `batallas/historial-general.json` se deja para un workflow separado que pueda consolidar archivos sin carreras entre subidas simultáneas.
