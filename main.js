// Compañera de escritorio: ventana transparente, sin bordes y siempre encima.
// Arranca el servidor de Python (servidor.py) por detrás y muestra la página en modo compañera.
//
// Variables de entorno opcionales:
//   HANA_PYTHON=C:\ruta\python.exe   forzar qué Python usar
//   HANA_SIN_GPU=1                   si ves fondo negro en vez de transparente
//   HANA_DEBUG=1                     abre las herramientas de desarrollo

const { app, BrowserWindow, Tray, Menu, ipcMain, globalShortcut, screen, nativeImage, dialog, session } =
  require("electron");
const path = require("path");
const fs = require("fs");
const http = require("http");
const { spawn, spawnSync } = require("child_process");

if (process.env.HANA_SIN_GPU) app.disableHardwareAcceleration();

const PUERTO = 8765;
const URL_BASE = `http://127.0.0.1:${PUERTO}`;
const ANCHO = 420;
const ALTO_BASE = 680;
const ATAJO_CHAT = "Control+Alt+R";
const ATAJO_MIC = "Control+Alt+M";
const ATAJO_QUIETA = "Control+Alt+Q";     // alternar entre caminar y quedarse quieta

let ventana = null;
let bandeja = null;
let alto = ALTO_BASE;

// ---------------------------------------------------------------------
//  Ajustes guardados (posición de la ventana y opciones del menú)
// ---------------------------------------------------------------------
let ajustes = { x: null, y: null, encima: true, clicAtraves: true, caminar: true };
const archivoAjustes = () => path.join(app.getPath("userData"), "ajustes.json");

function cargarAjustes() {
  try {
    ajustes = { ...ajustes, ...JSON.parse(fs.readFileSync(archivoAjustes(), "utf-8")) };
  } catch (e) { /* primera vez: valores por defecto */ }
}

function guardarAjustes() {
  try { fs.writeFileSync(archivoAjustes(), JSON.stringify(ajustes, null, 1)); } catch (e) {}
}

// ---------------------------------------------------------------------
//  Servidor de Python
// ---------------------------------------------------------------------
let servidor = null;
let servidorListo = false;
let sinMasIntentos = false;     // ya se probaron todos los Python posibles y ninguno arrancó
let salidaServidor = "";

// Ruta del servidor compilado (solo existe en la app empaquetada, dentro de resources/)
const exeServidor = () =>
  path.join(process.resourcesPath, "servidor", process.platform === "win32" ? "servidor.exe" : "servidor");

function entornoServidor() {
  const env = { ...process.env, PYTHONUTF8: "1", RYUKO_PUERTO: String(PUERTO) };
  if (app.isPackaged) {
    env.RYUKO_DATOS = app.getPath("userData");                       // historial y modelo de voz
    env.RYUKO_MODELO = path.join(process.resourcesPath, "modelo");   // modelo Live2D (puedes cambiarlo)
  }
  return env;
}

function lanzarServidor() {
  const empaquetada = app.isPackaged;   // app instalada: el servidor ya viene compilado
  const candidatos = empaquetada
    ? [[exeServidor(), []]]
    : process.env.HANA_PYTHON
      ? [[process.env.HANA_PYTHON, []]]
      : [["python", []], ["py", ["-3"]]];

  const probar = (i) => {
    if (i >= candidatos.length) {
      salidaServidor += empaquetada
        ? "\nNo pude arrancar el servidor integrado."
        : "\nNo pude arrancar el servidor con ningún Python (probé 'python' y 'py').";
      sinMasIntentos = true;
      return;
    }
    const [exe, previos] = candidatos[i];
    const hijo = spawn(
      exe,
      empaquetada
        ? []
        : [...previos, "-m", "uvicorn", "servidor:app", "--host", "127.0.0.1", "--port", String(PUERTO)],
      { cwd: empaquetada ? path.dirname(exe) : __dirname, windowsHide: true, env: entornoServidor() }
    );
    servidor = hijo;
    let avanzo = false;
    const siguiente = () => {
      if (avanzo) return;
      avanzo = true;
      if (servidor === hijo) servidor = null;
      probar(i + 1);
    };
    const guardar = (d) => { salidaServidor = (salidaServidor + d.toString()).slice(-2000); };
    hijo.stdout.on("data", guardar);
    hijo.stderr.on("data", guardar);
    hijo.on("error", siguiente);
    hijo.on("exit", (codigo) => {
      salidaServidor += `\n(${exe} terminó con código ${codigo})`;
      if (!servidorListo) siguiente();
      else if (servidor === hijo) servidor = null;
    });
  };
  probar(0);
}

let idioma = "es";                                       // lo informa el servidor (IDIOMA en servidor.py)
const T = (es, en) => (idioma === "en" ? en : es);       // textos del menú según el idioma

function responde() {
  return new Promise((resolver) => {
    const r = http.get(`${URL_BASE}/info`, (resp) => {
      let cuerpo = "";
      resp.on("data", (d) => { cuerpo += d; });
      resp.on("end", () => {
        try { idioma = JSON.parse(cuerpo).idioma === "en" ? "en" : "es"; } catch (e) { /* se queda como estaba */ }
        resolver(resp.statusCode === 200);
      });
    });
    r.on("error", () => resolver(false));
    r.setTimeout(1500, () => { r.destroy(); resolver(false); });
  });
}

async function esperarServidor(limiteMs) {
  const fin = Date.now() + limiteMs;
  while (Date.now() < fin) {
    if (await responde()) return true;
    if (sinMasIntentos) return false;      // no tiene sentido seguir esperando
    await new Promise((r) => setTimeout(r, 500));
  }
  return false;
}

function detenerServidor() {
  if (!servidor) return;
  const pid = servidor.pid;
  try {
    if (process.platform === "win32") {
      // Síncrono: la app puede cerrarse antes de que un taskkill asíncrono llegue a ejecutarse
      spawnSync("taskkill", ["/pid", String(pid), "/T", "/F"], { windowsHide: true });
    } else {
      servidor.kill();
    }
  } catch (e) {}
  servidor = null;
}

// ---------------------------------------------------------------------
//  Ventana
// ---------------------------------------------------------------------
function posicionVisible(x, y) {
  return screen.getAllDisplays().some(({ workArea: a }) =>
    x + 40 > a.x && x < a.x + a.width - 40 && y + 40 > a.y && y < a.y + a.height - 40);
}

function esquinaInferiorDerecha() {
  const a = screen.getPrimaryDisplay().workArea;
  return { x: a.x + a.width - ANCHO - 20, y: a.y + a.height - alto };
}

function crearVentana() {
  alto = Math.min(ALTO_BASE, screen.getPrimaryDisplay().workArea.height);
  const pos = (ajustes.x != null && ajustes.y != null && posicionVisible(ajustes.x, ajustes.y))
    ? { x: ajustes.x, y: ajustes.y }
    : esquinaInferiorDerecha();

  ventana = new BrowserWindow({
    width: ANCHO, height: alto, x: pos.x, y: pos.y,
    transparent: true, frame: false, resizable: false, hasShadow: false,
    skipTaskbar: true, show: false, backgroundColor: "#00000000",
    alwaysOnTop: ajustes.encima,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      autoplayPolicy: "no-user-gesture-required",   // permite que el saludo inicial tenga voz
    },
  });

  ventana.loadURL(`${URL_BASE}/?modo=companera`);
  ventana.once("ready-to-show", () => ventana.show());
  if (process.env.HANA_DEBUG) ventana.webContents.openDevTools({ mode: "detach" });

  let temporizador = null;
  ventana.on("move", () => {            // guardar la posición sin escribir en cada pixel
    clearTimeout(temporizador);
    temporizador = setTimeout(() => {
      if (!ventana) return;
      const [x, y] = ventana.getPosition();
      ajustes.x = x; ajustes.y = y;
      guardarAjustes();
    }, 400);
  });
  ventana.on("closed", () => { ventana = null; });
}

function abrirChat() {
  if (!ventana) return;
  ventana.show();
  ventana.focus();
  ventana.webContents.send("abrir-chat");
}

function escuchar() {              // muestra a la compañera y empieza a grabar con el micrófono
  if (!ventana) return;
  ventana.show();
  ventana.focus();
  ventana.webContents.send("escuchar");
}

function construirMenu() {
  bandeja.setContextMenu(Menu.buildFromTemplate([
    { label: T("Escribir", "Type") + `  (${ATAJO_CHAT.replace("Control", "Ctrl")})`, click: abrirChat },
    { label: T("Hablar con el micrófono", "Talk with the microphone") + `  (${ATAJO_MIC.replace("Control", "Ctrl")})`, click: escuchar },
    { label: T("Mostrar / ocultar", "Show / hide"), click: () => {
        if (!ventana) return;
        if (ventana.isVisible()) ventana.hide(); else ventana.show();
    } },
    { type: "separator" },
    { label: T("Caminar por la pantalla", "Walk around the screen") + `  (${ATAJO_QUIETA.replace("Control", "Ctrl")})`, type: "checkbox",
      checked: ajustes.caminar, click: (item) => alternarCaminar(item.checked) },
    { label: T("Siempre encima", "Always on top"), type: "checkbox", checked: ajustes.encima, click: (item) => {
        ajustes.encima = item.checked;
        if (ventana) ventana.setAlwaysOnTop(item.checked);
        guardarAjustes();
    } },
    { label: T("Dejar pasar los clics en las zonas vacías", "Let clicks through empty areas"), type: "checkbox",
      checked: ajustes.clicAtraves, click: (item) => {
        ajustes.clicAtraves = item.checked;
        if (!item.checked && ventana) ventana.setIgnoreMouseEvents(false);
        guardarAjustes();
    } },
    ...(app.isPackaged && process.platform === "win32" ? [{
      label: T("Iniciar con Windows", "Start with Windows"), type: "checkbox",
      checked: app.getLoginItemSettings().openAtLogin,
      click: (item) => app.setLoginItemSettings({ openAtLogin: item.checked }),
    }] : []),
    { type: "separator" },
    { label: T("Reiniciar conversación", "Reset conversation"), click: () => ventana && ventana.webContents.send("reiniciar") },
    { label: T("Ajustar expresiones", "Adjust expressions"), click: () => ventana && ventana.webContents.send("herramientas") },
    { label: T("Volver a la esquina de la pantalla", "Back to the screen corner"), click: () => {
        if (!ventana) return;
        const { x, y } = esquinaInferiorDerecha();
        ventana.show();
        ventana.setBounds({ x, y, width: ANCHO, height: alto });
    } },
    { type: "separator" },
    { label: T("Salir", "Quit"), click: () => app.quit() },
  ]));
}

function crearBandeja() {
  const icono = nativeImage.createFromPath(path.join(__dirname, "icono.png"))
    .resize({ width: 16, height: 16 });
  bandeja = new Tray(icono);
  bandeja.setToolTip(T("Compañera de escritorio", "Desktop companion"));
  construirMenu();
  bandeja.on("click", () => {
    if (!ventana) return;
    if (ventana.isVisible()) ventana.hide(); else ventana.show();
  });
}

// ---------------------------------------------------------------------
//  Paseo por la pantalla: camina por el borde inferior, se detiene si estás cerca o hablando con ella,
//  cae al suelo si la sueltas en el aire y te sigue con la mirada.
// ---------------------------------------------------------------------
const PASEO = {
  velocidad: 70,            // píxeles por segundo al caminar
  distanciaMin: 160, distanciaMax: 650,
  esperaMin: 5000, esperaMax: 16000,   // tiempo quieta entre un paseo y otro (ms)
  cerca: 120,               // si el cursor está a menos de esto (en horizontal) del personaje, se detiene
  gravedad: 2600,           // píxeles por segundo al cuadrado al caer
  margen: 110,              // cuánto puede salirse la ventana (transparente) por los bordes de la pantalla
  intervalo: 33,            // ms entre actualizaciones (~30 por segundo)
};
let paseo = { caminando: false, dir: 1, vel: 0, destino: 0, hasta: Date.now() + 4000, vy: 0 };
let ocupada = false;          // la página avisa: chat abierto, hablando, escuchando o burbuja visible
let ultimoArrastre = 0;
let ultimaMirada = { x: 0, y: 0, t: 0 };
let temporizadorPaseo = null;
let ultimoTick = Date.now();

const limitar = (v, a, b) => Math.max(a, Math.min(b, v));
const aleatorio = (a, b) => a + Math.random() * (b - a);

function avisarPaseo() {
  if (ventana && !ventana.isDestroyed()) {
    ventana.webContents.send("paseo", { caminando: paseo.caminando, dir: paseo.dir });
  }
}

function pararPaseo(esperaMs) {
  const estabaCaminando = paseo.caminando;
  paseo.caminando = false;
  paseo.vel = 0;
  paseo.hasta = Math.max(paseo.hasta, Date.now() + esperaMs);
  if (estabaCaminando) avisarPaseo();
}

function pasoDelPaseo() {
  const ahora = Date.now();
  const dt = Math.min(0.1, (ahora - ultimoTick) / 1000);
  ultimoTick = ahora;
  if (!ventana || ventana.isDestroyed() || !ventana.isVisible()) return;

  const b = ventana.getBounds();
  const area = screen.getDisplayMatching(b).workArea;
  const suelo = Math.max(area.y, area.y + area.height - alto);
  const cursor = screen.getCursorScreenPoint();

  // Mirada: hacia dónde está el cursor respecto de la cabeza (se avisa a la página unas 15 veces por segundo)
  const mx = limitar((cursor.x - (b.x + b.width / 2)) / 600, -1, 1);
  const my = limitar((cursor.y - (b.y + b.height * 0.2)) / 500, -1, 1);
  if (ahora - ultimaMirada.t > 66 && (Math.abs(mx - ultimaMirada.x) > 0.02 || Math.abs(my - ultimaMirada.y) > 0.02)) {
    ultimaMirada = { x: mx, y: my, t: ahora };
    ventana.webContents.send("mirada", { x: mx, y: my });
  }

  if (!ajustes.caminar) { if (paseo.caminando) pararPaseo(0); paseo.vy = 0; return; }

  // Si la están arrastrando, no hacer nada
  if (ahora - ultimoArrastre < 250) { pararPaseo(3000); paseo.vy = 0; return; }

  // Gravedad: si quedó en el aire, cae hasta el suelo
  if (b.y < suelo - 1) {
    pararPaseo(1500);
    paseo.vy += PASEO.gravedad * dt;
    const y = Math.min(suelo, b.y + paseo.vy * dt);
    ventana.setBounds({ x: b.x, y: Math.round(y), width: ANCHO, height: alto });
    return;
  }
  paseo.vy = 0;
  if (b.y !== suelo) { ventana.setBounds({ x: b.x, y: suelo, width: ANCHO, height: alto }); }

  // ¿Hay que quedarse quieta? (ocupada, o con el cursor encima de ella)
  const centro = b.x + b.width / 2;
  const cursorCerca = Math.abs(cursor.x - centro) < PASEO.cerca && cursor.y >= b.y && cursor.y <= b.y + b.height;
  if (ocupada || cursorCerca) { pararPaseo(cursorCerca ? 2500 : 1500); return; }

  const minX = area.x - PASEO.margen, maxX = area.x + area.width - b.width + PASEO.margen;
  if (!paseo.caminando) {
    if (ahora < paseo.hasta) return;
    // Elige un destino al azar a un lado u otro, dentro de la pantalla
    let dir = Math.random() < 0.5 ? -1 : 1;
    if (b.x - PASEO.distanciaMin < minX) dir = 1;
    else if (b.x + PASEO.distanciaMin > maxX) dir = -1;
    paseo.destino = limitar(b.x + dir * aleatorio(PASEO.distanciaMin, PASEO.distanciaMax), minX, maxX);
    paseo.dir = paseo.destino >= b.x ? 1 : -1;
    paseo.caminando = true;
    avisarPaseo();
  }

  // Caminar con aceleración suave
  paseo.vel += (PASEO.velocidad - paseo.vel) * Math.min(1, dt * 4);
  let x = b.x + paseo.dir * paseo.vel * dt;
  const llego = paseo.dir > 0 ? x >= paseo.destino : x <= paseo.destino;
  if (llego) x = paseo.destino;
  ventana.setBounds({ x: Math.round(x), y: suelo, width: ANCHO, height: alto });
  if (llego) {
    paseo.hasta = ahora + aleatorio(PASEO.esperaMin, PASEO.esperaMax);
    pararPaseo(0);
  }
}

function iniciarPaseo() {
  if (temporizadorPaseo) return;
  ultimoTick = Date.now();
  temporizadorPaseo = setInterval(() => { try { pasoDelPaseo(); } catch (e) { /* un fallo no debe tumbar la app */ } }, PASEO.intervalo);
}

function alternarCaminar(valor) {
  ajustes.caminar = typeof valor === "boolean" ? valor : !ajustes.caminar;
  if (!ajustes.caminar) pararPaseo(0);
  guardarAjustes();
  if (bandeja) construirMenu();
  return ajustes.caminar;
}

// ---------------------------------------------------------------------
//  Mensajes desde la página (preload.js)
// ---------------------------------------------------------------------
ipcMain.on("clic-atraves", (_e, ignorar) => {
  if (!ventana) return;
  // Con 'forward' la página sigue recibiendo el movimiento del ratón para saber cuándo volver a ser clicable
  ventana.setIgnoreMouseEvents(ajustes.clicAtraves ? !!ignorar : false, { forward: true });
});

ipcMain.on("ocupada", (_e, valor) => { ocupada = !!valor; });

ipcMain.on("mover", (_e, dx, dy) => {
  if (!ventana || !Number.isFinite(dx) || !Number.isFinite(dy)) return;
  ultimoArrastre = Date.now();
  const b = ventana.getBounds();
  // Se fija el tamaño en cada movimiento: evita que la ventana "crezca" con pantallas escaladas
  ventana.setBounds({ x: Math.round(b.x + dx), y: Math.round(b.y + dy), width: ANCHO, height: alto });
});

// ---------------------------------------------------------------------
//  Arranque y cierre
// ---------------------------------------------------------------------
async function arrancar() {
  cargarAjustes();

  // Permisos: solo el micrófono (nunca la cámara) y el portapapeles, y solo para nuestra propia página
  const nuestra = (origen) => String(origen || "").startsWith(URL_BASE);
  session.defaultSession.setPermissionRequestHandler((wc, permiso, responder, detalles) => {
    const url = (detalles && detalles.requestingUrl) || wc.getURL();
    const tipos = (detalles && detalles.mediaTypes) || [];
    responder(nuestra(url) &&
      ((permiso === "media" && !tipos.includes("video")) || permiso === "clipboard-sanitized-write"));
  });
  session.defaultSession.setPermissionCheckHandler((wc, permiso, origen, detalles) =>
    nuestra(origen) &&
    ((permiso === "media" && !(detalles && detalles.mediaType === "video")) ||
     permiso === "clipboard-sanitized-write"));

  if (!(await responde())) lanzarServidor();   // si ya hay un servidor en ese puerto, se reutiliza
  const ok = await esperarServidor(40000);
  if (!ok) {
    dialog.showErrorBox(
      app.isPackaged ? "No pude iniciar el servidor integrado" : "No pude iniciar el servidor de Python",
      (app.isPackaged
        ? "Prueba a cerrar otras copias de la app y volver a abrirla. Si el antivirus bloqueó servidor.exe, " +
          "añade una excepción.\n\n"
        : "Comprueba que Python esté instalado y que hayas ejecutado:\n" +
          "    pip install -r requirements.txt\n\n") +
      "Detalle:\n" + (salidaServidor.trim() || "(sin salida)")
    );
    app.quit();
    return;
  }
  servidorListo = true;

  crearVentana();
  crearBandeja();
  if (!globalShortcut.register(ATAJO_CHAT, abrirChat)) {
    console.warn(`No pude registrar el atajo ${ATAJO_CHAT} (¿lo usa otro programa?)`);
  }
  if (!globalShortcut.register(ATAJO_MIC, escuchar)) {
    console.warn(`No pude registrar el atajo ${ATAJO_MIC} (¿lo usa otro programa?)`);
  }
  if (!globalShortcut.register(ATAJO_QUIETA, () => alternarCaminar())) {
    console.warn(`No pude registrar el atajo ${ATAJO_QUIETA} (¿lo usa otro programa?)`);
  }
  iniciarPaseo();
}

if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on("second-instance", () => { if (ventana) ventana.show(); });
  app.on("window-all-closed", () => { /* sigue viva en la bandeja */ });
  app.on("will-quit", () => globalShortcut.unregisterAll());
  app.on("before-quit", () => { clearInterval(temporizadorPaseo); detenerServidor(); });
  // Ctrl+C en la consola (npm start) u otro programa que pida cerrar: salir limpio para no dejar el servidor huérfano
  for (const senal of ["SIGINT", "SIGTERM"]) process.on(senal, () => app.quit());
  app.whenReady().then(arrancar);
}
