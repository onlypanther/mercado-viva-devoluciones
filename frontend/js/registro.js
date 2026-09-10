/* Registro de clientes.

   Las validaciones de esta pantalla son por comodidad: avisan al usuario sin
   esperar al servidor. El backend vuelve a comprobar exactamente lo mismo,
   porque es el unico que no se puede saltar. */

const boton = document.getElementById("crear");
const campos = {
  nombre: document.getElementById("nombre"),
  documento: document.getElementById("documento"),
  email: document.getElementById("email"),
  password: document.getElementById("password"),
  password2: document.getElementById("password2"),
};

/* Mostrar u ocultar ambas contrasenas a la vez. Escribir dos veces una clave
   a ciegas es la primera causa de que alguien no pueda entrar despues. */
document.getElementById("ver").addEventListener("change", (e) => {
  const tipo = e.target.checked ? "text" : "password";
  campos.password.type = tipo;
  campos.password2.type = tipo;
});

function revisar() {
  const nombre = campos.nombre.value.trim();
  const documento = campos.documento.value.trim();
  const email = campos.email.value.trim();
  const password = campos.password.value;
  const password2 = campos.password2.value;

  if (nombre.length < 3) return "Escriba su nombre completo.";
  if (!/^\d{6,15}$/.test(documento.replace(/[.\s]/g, "")))
    return "El documento debe tener entre 6 y 15 dígitos, solo números.";
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email))
    return "Revise el correo: no parece una dirección válida.";
  if (password.length < 8)
    return "La contraseña debe tener al menos 8 caracteres.";
  if (!/[a-zA-Z]/.test(password) || !/\d/.test(password))
    return "La contraseña debe incluir al menos una letra y un número.";
  if (password !== password2)
    return "Las dos contraseñas no coinciden.";

  return null;
}

async function crearCuenta() {
  ocultarAviso("aviso");

  const problema = revisar();
  if (problema) {
    mostrarAviso("aviso", problema);
    return;
  }

  boton.disabled = true;
  boton.textContent = "Creando su cuenta…";

  try {
    const datos = await Api.enviar("/api/auth/registro", {
      nombre: campos.nombre.value.trim(),
      documento: campos.documento.value.trim(),
      email: campos.email.value.trim(),
      password: campos.password.value,
    });

    // El servidor devuelve la sesion ya iniciada, asi que no hay que pedirle
    // al usuario que escriba sus datos otra vez.
    Sesion.guardar(datos.access_token, datos.usuario);
    window.location.href = Sesion.paginaDeInicio(datos.usuario.rol);
  } catch (error) {
    mostrarAviso("aviso", error.message, "aviso--error", error.regla);
    boton.disabled = false;
    boton.textContent = "Crear mi cuenta";
  }
}

boton.addEventListener("click", crearCuenta);
Object.values(campos).forEach((campo) =>
  campo.addEventListener("keydown", (e) => { if (e.key === "Enter") crearCuenta(); }));

if (Sesion.token() && Sesion.usuario()) {
  window.location.href = Sesion.paginaDeInicio(Sesion.usuario().rol);
}
