# Welcome to your Expo app 👋

This is an [Expo](https://expo.dev) project created with [`create-expo-app`](https://www.npmjs.com/package/create-expo-app).

## Get started

1. Install dependencies

   ```bash
   npm install
   ```

2. Start the app

   ```bash
   npx expo start
   ```

In the output, you'll find options to open the app in a

- [development build](https://docs.expo.dev/develop/development-builds/introduction/)
- [Android emulator](https://docs.expo.dev/workflow/android-studio-emulator/)
- [iOS simulator](https://docs.expo.dev/workflow/ios-simulator/)
- [Expo Go](https://expo.dev/go), a limited sandbox for trying out app development with Expo

You can start developing by editing the files inside the **app** directory. This project uses [file-based routing](https://docs.expo.dev/router/introduction).

## Get a fresh project

When you're ready, run:

```bash
npm run reset-project
```

This command will move the starter code to the **app-example** directory and create a blank **app** directory where you can start developing.

### Other setup steps

- To set up ESLint for linting, run `npx expo lint`, or follow our guide on ["Using ESLint and Prettier"](https://docs.expo.dev/guides/using-eslint/)
- If you'd like to set up unit testing, follow our guide on ["Unit Testing with Jest"](https://docs.expo.dev/develop/unit-testing/)
- Learn more about the TypeScript setup in this template in our guide on ["Using TypeScript"](https://docs.expo.dev/guides/typescript/)

## Learn more

To learn more about developing your project with Expo, look at the following resources:

- [Expo documentation](https://docs.expo.dev/): Learn fundamentals, or go into advanced topics with our [guides](https://docs.expo.dev/guides).
- [Learn Expo tutorial](https://docs.expo.dev/tutorial/introduction/): Follow a step-by-step tutorial where you'll create a project that runs on Android, iOS, and the web.

## Join the community

Join our community of developers creating universal apps.

- [Expo on GitHub](https://github.com/expo/expo): View our open source platform and contribute.
- [Discord community](https://chat.expo.dev): Chat with Expo users and ask questions.


## Utilidades OPR

La aplicación incorpora una pestaña **Utilidades** con cinco herramientas offline:

- Sistema de tirada de dados
- Generador de escenarios
- Selector de misiones
- Eventos aleatorios
- Registro resultados

Los resultados generados se guardan localmente mediante AsyncStorage.

## Biblioteca de Manuales

Esta versión incluye una pestaña **Manuales** con los manuales de Grimdark Future suministrados por el usuario. Permite seleccionar ejército, buscar tropas/hechizos/reglas y abrir/compartir el PDF correspondiente.

La clasificación de unidades usa el catálogo derivado de esos manuales como fuente de existencia: si una unidad no aparece en el manual del ejército correspondiente, se clasifica como **Narrativas**. Las categorías de OPR se conservan para las unidades oficiales.


## V16
- Reserva explícita del área superior de la barra de estado Android para todas las pestañas.
- Iconos visibles en las cinco pestañas inferiores usando símbolos Unicode, sin dependencia adicional.


## V17
- Importación de JSON exportados por Army Forge desde Campañas.
- Importación de listas de batalla exportadas por la propia campaña.
- Pantallas de selección de campaña reorganizadas para evitar solapamientos.
- SafeArea global para respetar la barra de estado de Android en todas las pestañas.
- Restablecer utilidades sin cerrar la aplicación.
- Icono adaptativo Android con margen seguro para evitar recortes.


## Intro
- Reproduce el video `assets/opr-intro.mp4` al iniciar la aplicación y luego abre Ejército.
- Incluye opción para saltar la intro.
