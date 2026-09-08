/* Historial unificado: la vista que justifica la palabra "omnicanal". */

const usuario = Sesion.exigir(null);
if (usuario && !["ADMIN", "ASESOR"].includes(usuario.rol)) {
  window.location.href = Sesion.paginaDeInicio(usuario.rol);
}
pintarBarra(usuario);
conectarSalida();

const filtro = document.getElementById("filtro");

async function cargar() {
  const zona = document.getElementById("tabla");
  zona.innerHTML = `<p class="cargando">Cargando…</p>`;
  ocultarAviso("aviso");

  let solicitudes = [];
  try {
    const consulta = filtro.value ? `?estado=${encodeURIComponent(filtro.value)}` : "";
    solicitudes = await Api.obtener(`/api/devoluciones${consulta}`);
  } catch (error) {
    zona.innerHTML = "";
    mostrarAviso("aviso", error.message, "aviso--error", error.regla);
    return;
  }

  pintarResumen(solicitudes);

  if (solicitudes.length === 0) {
    zona.innerHTML = `<div class="vacio"><p style="margin:0">No hay devoluciones con este filtro.</p></div>`;
    return;
  }

  zona.innerHTML = `
    <div class="envoltura-tabla">
      <table class="tabla">
        <thead>
          <tr>
            <th>Código</th><th>Estado</th><th>Cliente</th><th>Pedido</th>
            <th>Reembolso</th><th>Tienda</th><th>Solicitada</th><th>Cerrada</th>
          </tr>
        </thead>
        <tbody>
          ${solicitudes.map((s) => `
            <tr>
              <td class="tabla__mono">${limpiar(s.codigo)}</td>
              <td><span class="estado ${Formato.claseEstado(s.estado)}">${Formato.estado(s.estado)}</span></td>
              <td>${limpiar(s.nombre_cliente)}<div class="linea__detalle tabla__mono">${limpiar(s.documento_cliente)}</div></td>
              <td class="tabla__mono">${limpiar(s.codigo_pedido)}</td>
              <td>${Formato.pesos(s.monto_reembolso)}</td>
              <td>${limpiar(s.tienda || "—")}</td>
              <td>${Formato.fecha(s.creada_en)}</td>
              <td>${Formato.fecha(s.cerrada_en)}</td>
            </tr>`).join("")}
        </tbody>
      </table>
    </div>`;
}

function pintarResumen(solicitudes) {
  const contar = (estado) => solicitudes.filter((s) => s.estado === estado).length;
  const aprobado = solicitudes
    .filter((s) => s.estado === "APROBADA")
    .reduce((suma, s) => suma + Number(s.monto_reembolso), 0);

  document.getElementById("resumen").innerHTML = `
    <div><div class="datos__rotulo">Solicitudes</div><div class="datos__valor">${solicitudes.length}</div></div>
    <div><div class="datos__rotulo">Pendientes</div><div class="datos__valor">${contar("PENDIENTE_VALIDACION")}</div></div>
    <div><div class="datos__rotulo">Aprobadas</div><div class="datos__valor">${contar("APROBADA")}</div></div>
    <div><div class="datos__rotulo">Rechazadas</div><div class="datos__valor">${contar("RECHAZADA")}</div></div>
    <div><div class="datos__rotulo">Expiradas</div><div class="datos__valor">${contar("EXPIRADA")}</div></div>
    <div><div class="datos__rotulo">Reembolso autorizado</div><div class="datos__valor">${Formato.pesos(aprobado)}</div></div>`;
}

filtro.addEventListener("change", cargar);
cargar();
