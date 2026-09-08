/* Modulo de tienda: el asesor teclea un codigo y decide. Nada mas. */

const usuario = Sesion.exigir("ASESOR");
pintarBarra(usuario);
conectarSalida();

const campoCodigo = document.getElementById("codigo");
const botonBuscar = document.getElementById("buscar");
const zonaDetalle = document.getElementById("detalle");

let solicitudActual = null;

async function buscar() {
  const codigo = campoCodigo.value.trim().toUpperCase();
  ocultarAviso("aviso");
  zonaDetalle.hidden = true;
  solicitudActual = null;

  if (!codigo) {
    mostrarAviso("aviso", "Escriba el código que le entregó el cliente.");
    campoCodigo.focus();
    return;
  }

  botonBuscar.disabled = true;
  botonBuscar.textContent = "Buscando…";

  try {
    solicitudActual = await Api.obtener(`/api/devoluciones/codigo/${encodeURIComponent(codigo)}`);
    pintarDetalle(solicitudActual);
  } catch (error) {
    /* El 410 no es un fallo del asesor: es una regla del negocio que hay que
       poder explicarle al cliente en el mostrador. Por eso lleva otro color. */
    const clase = error.estado === 410 ? "aviso--espera" : "aviso--error";
    mostrarAviso("aviso", error.message, clase, error.regla);
  } finally {
    botonBuscar.disabled = false;
    botonBuscar.textContent = "Buscar";
  }
}

function pintarDetalle(s) {
  const cerrada = s.estado !== "PENDIENTE_VALIDACION";

  zonaDetalle.hidden = false;
  zonaDetalle.innerHTML = `
    <div class="tarjeta">
      <div class="bloque__titulo">
        <h2>${limpiar(s.codigo)}</h2>
        <span class="estado ${Formato.claseEstado(s.estado)}">${Formato.estado(s.estado)}</span>
      </div>

      <div class="datos">
        <div><div class="datos__rotulo">Cliente</div><div class="datos__valor">${limpiar(s.nombre_cliente)}</div></div>
        <div><div class="datos__rotulo">Documento</div><div class="datos__valor datos__valor--mono">${limpiar(s.documento_cliente)}</div></div>
        <div><div class="datos__rotulo">Pedido</div><div class="datos__valor datos__valor--mono">${limpiar(s.codigo_pedido)}</div></div>
        <div><div class="datos__rotulo">Solicitada</div><div class="datos__valor">${Formato.fecha(s.creada_en)}</div></div>
        <div><div class="datos__rotulo">Vence</div><div class="datos__valor">${Formato.fecha(s.expira_en)}</div></div>
        <div><div class="datos__rotulo">Reembolso</div><div class="datos__valor">${Formato.pesos(s.monto_reembolso)}</div></div>
      </div>

      <h3>Productos que debe recibir</h3>
      <div style="border:1px solid var(--linea);border-radius:8px;margin-bottom:1.2rem">
        ${s.items.map((i) => `
          <div class="linea">
            <div class="datos__valor" style="width:2.5rem;text-align:center">${i.cantidad}</div>
            <div>
              <div class="linea__nombre">${limpiar(i.nombre)}</div>
              <div class="linea__detalle">${limpiar(i.sku)}</div>
            </div>
            <div class="linea__detalle">${Formato.pesos(i.subtotal)}</div>
          </div>`).join("")}
      </div>

      <h3>Motivo declarado por el cliente</h3>
      <p>${limpiar(s.motivo)}</p>

      ${cerrada ? pintarCierre(s) : pintarFormularioDecision()}

      <h3 style="margin-top:1.5rem">Trazabilidad</h3>
      <ol class="rastro">
        ${s.historial.map((h) => `
          <li>
            <div>${Formato.estado(h.estado_nuevo)}</div>
            <div class="rastro__quien">${limpiar(h.nombre_usuario)}</div>
            <div class="rastro__cuando">${Formato.fecha(h.fecha)}${h.motivo ? " · " + limpiar(h.motivo) : ""}</div>
          </li>`).join("")}
      </ol>
    </div>`;

  if (!cerrada) {
    document.getElementById("aprobar").addEventListener("click", () => decidir(true));
    document.getElementById("rechazar").addEventListener("click", () => decidir(false));
  }
}

function pintarFormularioDecision() {
  return `
    <div class="campo" style="margin-top:1.4rem">
      <label for="observacion">Observación de la verificación</label>
      <textarea id="observacion"
                placeholder="Ejemplo: producto recibido en su empaque original, raya visible en la base"></textarea>
      <div class="campo__nota">Queda registrada con su nombre y la fecha. Mínimo 5 caracteres.</div>
    </div>
    <div class="decision">
      <button id="aprobar" class="boton boton--principal boton--grande">Aprobar la devolución</button>
      <button id="rechazar" class="boton boton--peligro boton--grande">Rechazar</button>
    </div>`;
}

function pintarCierre(s) {
  return `
    <div class="aviso ${s.estado === "APROBADA" ? "aviso--exito" : "aviso--espera"}" style="margin-top:1.2rem">
      Esta solicitud ya fue cerrada el ${Formato.fecha(s.cerrada_en)}${s.tienda ? " en " + limpiar(s.tienda) : ""}.
      ${s.observacion_asesor ? "<br>Observación: " + limpiar(s.observacion_asesor) : ""}
    </div>`;
}

async function decidir(aprobar) {
  const observacion = document.getElementById("observacion").value.trim();
  ocultarAviso("aviso");

  if (observacion.length < 5) {
    mostrarAviso("aviso", "Escriba una observación de al menos 5 caracteres antes de decidir.");
    return;
  }

  const botones = zonaDetalle.querySelectorAll("button");
  botones.forEach((b) => (b.disabled = true));

  try {
    const actualizada = await Api.enviar(
      `/api/devoluciones/${encodeURIComponent(solicitudActual.codigo)}/decision`,
      { aprobar, observacion });

    solicitudActual = actualizada;
    pintarDetalle(actualizada);
    mostrarAviso("aviso",
      aprobar
        ? `Devolución aprobada. Reembolso autorizado por ${Formato.pesos(actualizada.monto_reembolso)}.`
        : "Devolución rechazada. El cliente puede consultar el motivo en su cuenta.",
      "aviso--exito");
    campoCodigo.value = "";
    campoCodigo.focus();
  } catch (error) {
    mostrarAviso("aviso", error.message,
      error.estado === 409 ? "aviso--espera" : "aviso--error", error.regla);
    botones.forEach((b) => (b.disabled = false));
  }
}

botonBuscar.addEventListener("click", buscar);
campoCodigo.addEventListener("keydown", (e) => { if (e.key === "Enter") buscar(); });
