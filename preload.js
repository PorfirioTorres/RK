// Puente seguro entre la página y Electron: solo expone estas funciones concretas.
const { contextBridge, ipcRenderer } = require("electron");

const escuchar = (canal, funcion) => ipcRenderer.on(canal, () => funcion());
const conDatos = (canal, funcion) => ipcRenderer.on(canal, (_e, datos) => funcion(datos));

contextBridge.exposeInMainWorld("escritorio", {
  clicAtraves: (ignorar) => ipcRenderer.send("clic-atraves", !!ignorar),
  mover: (dx, dy) => ipcRenderer.send("mover", dx, dy),
  alAbrirChat: (f) => escuchar("abrir-chat", f),
  alReiniciar: (f) => escuchar("reiniciar", f),
  alAlternarHerramientas: (f) => escuchar("herramientas", f),
  alEscuchar: (f) => escuchar("escuchar", f),
  ocupada: (valor) => ipcRenderer.send("ocupada", !!valor),
  alPaseo: (f) => conDatos("paseo", f),         // {caminando, dir}
  alMirar: (f) => conDatos("mirada", f),        // {x, y} entre -1 y 1: hacia dónde está el cursor
});
