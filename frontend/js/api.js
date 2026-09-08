/* Cliente HTTP. Adjunta el token y convierte cualquier fallo en un objeto
   uniforme { mensaje, regla, estado }, para que las pantallas nunca tengan
   que interpretar codigos HTTP a mano. */

class ErrorApi extends Error {
  constructor(mensaje, regla, estado) {
    super(mensaje);
    this.regla = regla;
    this.estado = estado;
  }
}

const Api = {
  async peticion(ruta, opciones = {}) {
    const cabeceras = { "Content-Type": "application/json", ...(opciones.headers || {}) };
    const token = Sesion.token();
    if (token) cabeceras["Authorization"] = `Bearer ${token}`;

    let respuesta;
    try {
      respuesta = await fetch(`${API}${ruta}`, { ...opciones, headers: cabeceras });
    } catch {
      throw new ErrorApi(
        "No se pudo conectar con el servidor. Revise la conexion e intente de nuevo.",
        null, 0);
    }

    if (respuesta.status === 401) {
      Sesion.cerrar();
      throw new ErrorApi("La sesion vencio. Inicie sesion de nuevo.", null, 401);
    }

    let cuerpo = null;
    try { cuerpo = await respuesta.json(); } catch { /* respuesta sin cuerpo */ }

    if (!respuesta.ok) {
      throw new ErrorApi(
        this.mensajeDeError(cuerpo, respuesta.status),
        cuerpo?.regla ?? null,
        respuesta.status);
    }
    return cuerpo;
  },

  /* FastAPI devuelve dos formatos distintos: el del manejador de dominio
     ({tipo, mensaje, regla}) y el de Pydantic ({detail: [...]}). Se unifican
     aqui para que la pantalla muestre siempre una frase legible. */
  mensajeDeError(cuerpo, estado) {
    if (cuerpo?.mensaje) return cuerpo.mensaje;
    if (Array.isArray(cuerpo?.detail)) {
      return cuerpo.detail
        .map((d) => `${(d.loc || []).slice(1).join(".")}: ${d.msg}`)
        .join(" · ");
    }
    if (typeof cuerpo?.detail === "string") return cuerpo.detail;
    return `El servidor respondio con un error (${estado}).`;
  },

  obtener(ruta) { return this.peticion(ruta); },
  enviar(ruta, datos) {
    return this.peticion(ruta, { method: "POST", body: JSON.stringify(datos) });
  },
};

/* ---------- Utilidades compartidas por las tres pantallas ---------------- */

const Formato = {
  pesos(valor) {
    return new Intl.NumberFormat("es-CO", {
      style: "currency", currency: "COP", maximumFractionDigits: 0,
    }).format(Number(valor || 0));
  },
  fecha(iso) {
    if (!iso) return "—";
    return new Date(iso).toLocaleString("es-CO", {
      day: "2-digit", month: "short", year: "numeric",
      hour: "2-digit", minute: "2-digit",
    });
  },
  horasRestantes(iso) {
    const faltan = (new Date(iso) - new Date()) / 36e5;
    if (faltan <= 0) return "vencido";
    if (faltan < 1) return `${Math.round(faltan * 60)} minutos`;
    return `${Math.floor(faltan)} horas`;
  },
  estado(valor) {
    return {
      PENDIENTE_VALIDACION: "Pendiente de validar",
      APROBADA: "Aprobada", RECHAZADA: "Rechazada", EXPIRADA: "Expirada",
    }[valor] || valor;
  },
  claseEstado(valor) {
    return {
      PENDIENTE_VALIDACION: "estado--pendiente", APROBADA: "estado--aprobada",
      RECHAZADA: "estado--rechazada", EXPIRADA: "estado--expirada",
    }[valor] || "estado--expirada";
  },
};

/* Escapa el texto antes de insertarlo en el HTML. Los motivos y las
   observaciones los escribe el usuario, asi que no pueden confiarse. */
function limpiar(texto) {
  const nodo = document.createElement("div");
  nodo.textContent = texto ?? "";
  return nodo.innerHTML;
}

function mostrarAviso(id, mensaje, clase = "aviso--error", regla = null) {
  const nodo = document.getElementById(id);
  nodo.className = `aviso ${clase}`;
  nodo.innerHTML = limpiar(mensaje) +
    (regla ? `<span class="aviso__regla">Regla del negocio aplicada: ${limpiar(regla)}</span>` : "");
  nodo.hidden = false;
  nodo.scrollIntoView({ block: "nearest" });
}

function ocultarAviso(id) { document.getElementById(id).hidden = true; }

function pintarBarra(usuario) {
  const nodo = document.getElementById("usuario-barra");
  if (!nodo || !usuario) return;
  nodo.textContent = usuario.tienda
    ? `${usuario.nombre} · ${usuario.tienda}`
    : usuario.nombre;
}

function conectarSalida() {
  const boton = document.getElementById("salir");
  if (boton) boton.addEventListener("click", () => Sesion.cerrar());
}
