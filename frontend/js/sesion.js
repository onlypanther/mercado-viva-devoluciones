/* Guarda el token de la sesion.

   Se usa sessionStorage y no localStorage a proposito: el asesor trabaja en
   un computador compartido de la tienda, y sessionStorage se borra al cerrar
   el navegador. Si el almacenamiento no esta disponible, se cae a memoria,
   de modo que la aplicacion nunca deja de funcionar por eso. */

const Sesion = (() => {
  let respaldo = {};

  function leer(clave) {
    try { return sessionStorage.getItem(clave); } catch { return respaldo[clave] ?? null; }
  }
  function escribir(clave, valor) {
    try { sessionStorage.setItem(clave, valor); } catch { respaldo[clave] = valor; }
  }
  function borrar() {
    try { sessionStorage.clear(); } catch { respaldo = {}; }
  }

  return {
    guardar(token, usuario) {
      escribir("viva_token", token);
      escribir("viva_usuario", JSON.stringify(usuario));
    },
    token() { return leer("viva_token"); },
    usuario() {
      try { return JSON.parse(leer("viva_usuario") || "null"); } catch { return null; }
    },
    cerrar() { borrar(); window.location.href = "index.html"; },

    /* Cada pagina declara que rol exige. Si no coincide, se devuelve al inicio. */
    exigir(rol) {
      const usuario = this.usuario();
      if (!this.token() || !usuario) { window.location.href = "index.html"; return null; }
      if (rol && usuario.rol !== rol) { window.location.href = "index.html"; return null; }
      return usuario;
    },

    paginaDeInicio(rol) {
      return { CLIENTE: "cliente.html", ASESOR: "tienda.html", ADMIN: "historial.html" }[rol]
        || "index.html";
    },
  };
})();
