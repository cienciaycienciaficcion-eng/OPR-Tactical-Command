# Registro OPR Tactical Command: decisión e implementación

- Registro cerrado por invitación.
- Identidad verificada mediante GitHub Device Flow.
- Perfil independiente con `display_name` personalizable.
- Ejércitos privados almacenados en PostgreSQL.
- Compartir es una acción explícita que publica una copia en el repositorio central.
- Las invitaciones se almacenan como SHA-256, expiran y admiten un máximo de usos.
- `ADMIN_API_TOKEN` permite al operador autorizado emitir invitaciones; nunca debe incluirse en la app.

## Despliegue seguro

1. Crear una base PostgreSQL en Render.
2. Configurar `DATABASE_URL` en el servicio web.
3. Crear `ADMIN_API_TOKEN` con un generador criptográficamente seguro.
4. Confirmar permisos de Contents read/write de la GitHub App.
5. Desplegar y comprobar `/health/database`.
6. Emitir una invitación de prueba, registrar una cuenta de prueba y comprobar que un ejército recién creado queda en PostgreSQL y no aparece como archivo en el repositorio.
7. Solo después conectar la interfaz móvil.

## Limitación de este ZIP

El archivo recibido no contiene los archivos de interfaz de React Native/Expo (`app/`, `src/`, etc.). El backend queda preparado, pero el formulario móvil de invitación, el perfil y el selector de visibilidad deben integrarse en el ZIP de la aplicación que incluya esas carpetas.
