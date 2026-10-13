# OPR Offline App V7

## Iconos Army Forge offline

El proyecto incluye las 47 URLs del CDN de Army Forge en:

`scripts/armyforge-icons.json`

En Windows, dentro de la carpeta del proyecto:

```bat
npm install
npm run download-icons
npm start
```

`download-icons` descarga las imágenes directamente desde el CDN de Army Forge, las guarda en `assets/faction_icons/` y genera `src/data_faction_icons.ts` con `require()` locales. Después de eso los iconos funcionan sin conexión.

## Cambios V7

- Manuales reorganizados con divisiones tipo Army Forge: Heroes, Core Units, Light Vehicles / Small Monsters, Vehicles / Monsters, Artillery, Titans, Aircraft y Narrative Heroes.
- Cada unidad muestra perfil, armas, habilidades y reglas.
- Las habilidades/reglas se pueden abrir directamente en la biblioteca de reglas OPR.
- Se muestran las modificaciones disponibles del Army Book, agrupadas por sección, con coste y efectos.
- Registro de batalla: hasta 4 jugadores y 4 rondas.
- Puntos de misión principal y secundaria por ronda.
- Registro de bajas/unidades perdidas por jugador.
- Reporte de batalla con resultado y bajas.
- Eliminación individual de batallas guardadas y borrado total del historial.
- Generador de escenarios con los 18 estilos de despliegue del HTML original, tres opciones de mapa por escenario, objetivos, terreno y modo de abordaje.
- Se mantienen las utilidades de dados con características del arma, calidad, beneficios de atacante/defensor y rangos de impacto/bloqueo.
- No se incluyen PDFs.

## Nota

La clasificación de unidades se genera a partir de los Army Books locales y de las reglas/etiquetas disponibles en sus datos. Para los grupos sin etiqueta explícita se usa la clasificación existente del catálogo como respaldo.

## V8
- Iconos Army Forge en tarjetas grandes con fondo blanco y mejor contraste.
- Botón CREAR Y CONTINUAR colocado al inicio del paso de aliados.
- Unidades muertas de campaña permanecen en el roster, marcadas con ☠️ y no seleccionables.
- Mapas de escenarios conservan proporción 6:4 para GF y 1:1 para Firefight/Skirmish/Abordaje.

## V9 — Campaña: bajas permanentes + paletas por sección
- Las unidades marcadas como muertas permanecen registradas en el ejército de campaña.
- Las unidades muertas siguen pudiendo abrirse con `Editar` para modificar su ficha/equipamiento; no participan en batalla ni reciben desarrollo/subidas de nivel.
- Nueva acción `☠️ Marcar muerta`: marca la unidad como muerta sin devolver sus puntos.
- Eliminar/retirar una unidad de la lista sí devuelve a la tesorería el coste actual de la unidad (base + mejoras + niveles + ajuste de campaña).
- La eliminación pide confirmación y muestra exactamente cuántos puntos se devuelven.
- Las unidades muertas/no disponibles quedan excluidas de la asignación de XP de nuevas misiones.
- Manuales: nueva paleta verde tipo Pip-Boy.
- Utilidades: nueva paleta verde tipo Pip-Boy.
- Reglas: nueva paleta azul.
- La barra de pestañas usa verde activo para Manuales/Utilidades y azul activo para Reglas.


## V10 — Campaña: muertas separadas + modificadores de dados
- Las unidades marcadas como muertas se muestran únicamente en el sector `☠️ UNIDADES MUERTAS`, al final del ejército.
- Una unidad muerta no puede editarse, recibir mejoras, vender mejoras, ganar XP, desarrollarse, subir de nivel ni vincularse.
- Una unidad muerta permanece registrada y conserva sus puntos invertidos; eliminarla definitivamente devuelve su coste actual a la tesorería.
- El lanzador de dados incorpora modificadores explícitos de -2 a +2 para impacto y defensa, incluyendo `+1`.

## V12
- Generador de escenarios con una paleta verde más oscura y contrastada.
- Textos del generador aclarados para mejorar legibilidad sobre fondos verdes oscuros.
- Controles de selección, botón de generación y panel de resultado con tonos verdes oscuros diferenciados.
- Se mantiene la proporción de mapas: GF 6:4 y Firefight/Skirmish/Abordaje 1:1.


## V15
- Android: back button returns through campaign subviews/modals instead of closing the app.
- Campaign UI: additional back handling for battle/unit editing states.
- Utilities: vertical launcher menu with separate screens for dice, scenarios and battle report.
- Manuals: faction reference image is displayed inside an explicit white container using contain mode.
