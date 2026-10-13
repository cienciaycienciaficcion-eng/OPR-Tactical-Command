# OPR Tactical Command v1.2.0 — cambios implementados

## Perfil y GitHub
- Perfil local y acceso mediante GitHub OAuth Device Flow (no se incorpora Client Secret a la APK).
- El Client ID público se configura en la pantalla de cuenta; la OAuth App debe tener Device Flow habilitado.
- El token de acceso se guarda en `expo-secure-store` en Android y no se persiste en AsyncStorage.
- Subida de ejércitos como JSON compatible con el importador de esta aplicación en `ejercitos/`.
- Los reportes de Battle Companion se guardan individualmente en `batallas/AAAA/` y se agregan a `batallas/historial-general.json`.
- La cuenta autenticada necesita permiso de escritura sobre el repositorio central. OAuth no concede acceso automáticamente a colaboradores que no estén autorizados en el repositorio.

## Battle Companion
- Nombre de cada jugador y selección de macrofacción: Imperio, Xenos o Caos.
- Al finalizar se genera un reporte con puntuación por ronda, unidades restantes, acciones registradas y macrofacciones.
- El reporte se agrega al historial general compartido con Registro de batalla, que ahora muestra tanto partidas estándar como Battle Companion.

## JSON / sincronización
- El importador del Army Roster admite `list.units`, `units`, `army.units` y `roster.units`.
- Si no puede resolver un ID de unidad local pero el JSON incluye una instantánea (`unitSnapshot`, `modifiedUnit`, `unitData`, `unit` o `data`), intenta conservar esa unidad en lugar de descartarla.
- Battle Companion resuelve referencias de Army Forge contra los libros de facción locales, y conserva instantáneas, mejoras, armas y hechizos explícitos cuando existen.
- La subida a GitHub incluye referencias de unidades y `unitSnapshot` para permitir volver a importar la lista sin perder los datos locales.

## Army Roster
- Cada unidad muestra movimiento (valor explícito si existe; si no, movimiento base OPR de 6", con ajuste mostrado para Fast/Slow), regla Tough(X) si está disponible y calidad/defensa.
- Se muestra un panel consolidado de reglas especiales de unidad, mejoras y objetos.
- Las unidades con Caster muestran los hechizos disponibles en el libro de su facción.

## Validación realizada
- Se requiere instalar la dependencia `expo-secure-store` y ejecutar la compilación local.
- No se ejecutó una compilación Android completa. Antes de distribuir, configurar el Client ID público de la OAuth App, probar Device Flow en un dispositivo y verificar los permisos de escritura del repositorio central.


## Configuración OAuth requerida antes de compilar/distribuir
1. En GitHub, crear una OAuth App para OPR Tactical Command y habilitar **Device Flow** en sus opciones.
2. Copiar el **Client ID** público en la pantalla “Usuario y sincronización con GitHub”. No usar ni distribuir el Client Secret en la APK.
3. Conceder a cada usuario permiso de escritura sobre `cienciaycienciaficcion-eng/OPR-Tactical-Command` (por ejemplo, como colaborador o miembro con permisos adecuados). OAuth autentica al usuario, pero no le concede acceso a repositorios donde no tiene permisos.
4. En Android, el token OAuth se guarda con `expo-secure-store`. La opción de cerrar sesión elimina el token local; para revocar acceso también se debe retirar la autorización desde la configuración de GitHub.
5. Cada reporte Companion se escribe en `batallas/AAAA/` y se indexa en `batallas/historial-general.json`. Desde la pantalla de cuenta se puede descargar y combinar el historial compartido con el local.

**Limitación de arquitectura:** si se necesita que cualquier jugador pueda subir resultados sin convertirse en colaborador del repositorio, hará falta un backend autenticado o una GitHub App instalada en la organización; no debe resolverse embebiendo una credencial de escritura compartida en la APK.
