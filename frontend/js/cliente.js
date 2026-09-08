/* Portal del cliente: elegir productos, escribir el motivo y obtener el codigo. */

const usuario = Sesion.exigir("CLIENTE");
pintarBarra(usuario);
conectarSalida();

let pedidos = [];

/* ---------- Pedidos elegibles (HU-01) ----------------------------------- */
async function cargarPedidos() {
  const zona = document.getElementById("pedidos");
  try {
    pedidos = await Api.obtener("/api/pedidos/elegibles");
  } catch (error) {
    zona.innerHTML = "";
    mostrarAviso("aviso", error.message, "aviso--error", error.regla);
    return;
  }

  if (pedidos.length === 0) {
    zona.innerHTML = `
      <div class="vacio">
        <h3>No tiene pedidos para devolver</h3>
        <p style="margin:0 auto">Aquí aparecerán sus compras entregadas dentro de los últimos 30 días.</p>
      </div>`;
    return;
  }

  zona.innerHTML = pedidos.map(pintarPedido).join("");
  zona.querySelectorAll("[data-enviar]").forEach((boton) =>
    boton.addEventListener("click", () => enviarSolicitud(Number(boton.dataset.enviar))));
}

function pintarPedido(pedido) {
  const lineas = pedido.items.map((item) => {
    const restantes = item.cantidad - item.cantidad_devuelta;
    if (!item.devolvible) {
      return `
        <div class="linea linea--bloqueada">
          <div style="width:5.5rem"></div>
          <div>
            <div class="linea__nombre">${limpiar(item.nombre)}</div>
            <div class="linea__detalle">${limpiar(item.sku)} · ${item.cantidad} unidad(es)</div>
          </div>
          <div class="linea__motivo">${limpiar(item.motivo_no_devolvible || "No devolvible")}</div>
        </div>`;
    }
    return `
      <div class="linea">
        <div class="linea__cantidad">
          <label class="sr" for="cant-${item.id}">Cantidad a devolver de ${limpiar(item.nombre)}</label>
          <input id="cant-${item.id}" type="number" min="0" max="${restantes}" value="0"
                 data-item="${item.id}" data-pedido="${pedido.id}">
        </div>
        <div>
          <div class="linea__nombre">${limpiar(item.nombre)}</div>
          <div class="linea__detalle">
            ${limpiar(item.sku)} · ${Formato.pesos(item.precio_unitario)} c/u ·
            puede devolver hasta ${restantes}
          </div>
        </div>
        <div class="linea__detalle">${Formato.pesos(item.precio_unitario * restantes)}</div>
      </div>`;
  }).join("");

  return `
    <article class="pedido">
      <div class="pedido__cabecera">
        <span class="pedido__codigo">${limpiar(pedido.codigo_pedido)}</span>
        <span class="pedido__meta">Entregado el ${Formato.fecha(pedido.fecha_entrega)} · compra por ${pedido.canal.toLowerCase()}</span>
        <span class="pedido__plazo">Quedan ${pedido.dias_restantes} días de plazo</span>
      </div>
      ${lineas}
      <div style="padding:1.1rem;border-top:1px solid var(--linea)">
        <div class="campo">
          <label for="motivo-${pedido.id}">¿Por qué desea devolverlo?</label>
          <textarea id="motivo-${pedido.id}"
                    placeholder="Ejemplo: el producto llegó con la superficie rayada"></textarea>
          <div class="campo__nota">Mínimo 10 caracteres. El asesor de la tienda leerá este texto.</div>
        </div>
        <button class="boton boton--principal" data-enviar="${pedido.id}">Generar código de devolución</button>
      </div>
    </article>`;
}

/* ---------- Crear la solicitud (HU-02 y HU-03) -------------------------- */
async function enviarSolicitud(pedidoId) {
  ocultarAviso("aviso");

  const items = [...document.querySelectorAll(`input[data-pedido="${pedidoId}"]`)]
    .map((campo) => ({ item_pedido_id: Number(campo.dataset.item), cantidad: Number(campo.value) }))
    .filter((linea) => linea.cantidad > 0);

  const motivo = document.getElementById(`motivo-${pedidoId}`).value.trim();

  /* Validacion en el navegador para dar respuesta inmediata. El servidor
     vuelve a validar lo mismo: esta capa es comodidad, no seguridad. */
  if (items.length === 0) {
    mostrarAviso("aviso", "Indique al menos una unidad para devolver.");
    return;
  }
  if (motivo.length < 10) {
    mostrarAviso("aviso", "Escriba el motivo con al menos 10 caracteres.");
    return;
  }

  const boton = document.querySelector(`[data-enviar="${pedidoId}"]`);
  boton.disabled = true;
  boton.textContent = "Generando…";

  try {
    const solicitud = await Api.enviar("/api/devoluciones",
      { pedido_id: pedidoId, motivo, items });
    pintarTalon(solicitud);
    await Promise.all([cargarPedidos(), cargarSolicitudes()]);
  } catch (error) {
    mostrarAviso("aviso", error.message, "aviso--error", error.regla);
    boton.disabled = false;
    boton.textContent = "Generar código de devolución";
  }
}

/* ---------- El talon: lo unico que el cliente necesita llevar ----------- */
function pintarTalon(solicitud) {
  const zona = document.getElementById("zona-talon");
  zona.hidden = false;
  zona.innerHTML = `
    <div class="aviso aviso--exito">
      Solicitud registrada. Preséntese en cualquier tienda VIVA con el producto y este código.
    </div>
    <div class="talon">
      <div class="talon__marco">
        <div>
          <div class="talon__rotulo">Código de devolución</div>
          <p class="talon__codigo">${limpiar(solicitud.codigo)}</p>
          <div class="talon__vence">
            Vence el ${Formato.fecha(solicitud.expira_en)} · quedan ${Formato.horasRestantes(solicitud.expira_en)}
          </div>
        </div>
        <div class="talon__monto">
          <div class="talon__rotulo">Reembolso estimado</div>
          <div class="talon__cifra">${Formato.pesos(solicitud.monto_reembolso)}</div>
          <div class="talon__vence">Se autoriza cuando el asesor verifique el producto</div>
        </div>
      </div>
    </div>`;
  zona.scrollIntoView({ behavior: "smooth", block: "start" });
}

/* ---------- Solicitudes anteriores -------------------------------------- */
async function cargarSolicitudes() {
  const zona = document.getElementById("solicitudes");
  let solicitudes = [];
  try {
    solicitudes = await Api.obtener("/api/devoluciones/mias");
  } catch (error) {
    zona.innerHTML = `<p class="cargando">${limpiar(error.message)}</p>`;
    return;
  }

  if (solicitudes.length === 0) {
    zona.innerHTML = `<div class="vacio"><p style="margin:0">Todavía no ha solicitado ninguna devolución.</p></div>`;
    return;
  }

  zona.innerHTML = solicitudes.map((s) => `
    <article class="pedido">
      <div class="pedido__cabecera">
        <span class="pedido__codigo">${limpiar(s.codigo)}</span>
        <span class="estado ${Formato.claseEstado(s.estado)}">${Formato.estado(s.estado)}</span>
        <span class="pedido__meta">Pedido ${limpiar(s.codigo_pedido)} · ${Formato.pesos(s.monto_reembolso)}</span>
      </div>
      <div style="padding:1rem 1.1rem">
        <p style="margin-bottom:.6rem">${limpiar(s.motivo)}</p>
        <ol class="rastro">
          ${s.historial.map((h) => `
            <li>
              <div>${Formato.estado(h.estado_nuevo)}</div>
              <div class="rastro__quien">${limpiar(h.nombre_usuario)}</div>
              <div class="rastro__cuando">${Formato.fecha(h.fecha)}${h.motivo ? " · " + limpiar(h.motivo) : ""}</div>
            </li>`).join("")}
        </ol>
      </div>
    </article>`).join("");
}

cargarPedidos();
cargarSolicitudes();
