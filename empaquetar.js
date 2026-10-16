// Convierte la app de Electron en una carpeta ejecutable (Ryuko.exe en Windows).
// Uso:  node empaquetar.js [win32|linux|darwin]      (por defecto, la plataforma actual)
//
// Antes hay que haber compilado el servidor:  python -m PyInstaller servidor.spec ...  (lo hace construir_exe.bat)
// Resultado: release/Ryuko-<plataforma>-x64/   con  resources/servidor/  y  resources/modelo/  dentro.

const path = require("path");
const fs = require("fs");

async function main() {
  // @electron/packager 20 es un módulo ESM: se carga con import() para que funcione con cualquier versión de Node
  const { packager } = await import("@electron/packager");

  const plataforma = process.argv[2] || process.platform;
  const raiz = __dirname;
  const servidor = path.join(raiz, "dist", "servidor");
  const modelo = path.join(raiz, "modelo");
  const icono = path.join(raiz, "icono.ico");

  for (const [nombre, ruta] of [["el servidor compilado (dist/servidor)", servidor], ["la carpeta modelo", modelo]]) {
    if (!fs.existsSync(ruta)) {
      console.error(`Falta ${nombre}. Ejecuta primero construir_exe.bat (o el paso de PyInstaller).`);
      process.exit(1);
    }
  }

  // Solo estos archivos van dentro de la app; el servidor y el modelo viajan aparte como "recursos".
  const PERMITIDOS = new Set(["/main.js", "/preload.js", "/icono.png", "/package.json"]);
  const ignorar = (ruta) => ruta !== "" && !PERMITIDOS.has(ruta);

  const opciones = {
    dir: raiz,
    name: "Ryuko",
    platform: plataforma,
    arch: "x64",
    out: path.join(raiz, "release"),
    overwrite: true,
    asar: true,
    prune: false,                       // no hay dependencias de ejecución que podar
    ignore: ignorar,
    extraResource: [servidor, modelo],  // se copian a resources/servidor y resources/modelo
    electronVersion: require("electron/package.json").version,
  };
  // Poner el ícono al .exe necesita rcedit (en Windows funciona solo; desde otros sistemas haría falta Wine)
  if (plataforma === "win32" && process.platform === "win32" && fs.existsSync(icono)) opciones.icon = icono;

  const rutas = await packager(opciones);
  console.log("\nListo:\n  " + rutas.join("\n  "));
}

main().catch((error) => {
  console.error("No pude empaquetar:", error);
  process.exit(1);
});
