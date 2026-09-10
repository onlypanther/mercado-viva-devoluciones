# Mercado VIVA — Devolución de una compra digital en una tienda física

MVP del proceso de devolución omnicanal para la cadena de supermercados Mercado VIVA.
Un cliente solicita la devolución desde la web, recibe un código con vigencia de 72 horas
y lo presenta en cualquier tienda física, donde un asesor verifica el producto y cierra
el caso con trazabilidad completa.

- **Aplicación publicada:** https://mercado-viva-devoluciones.vercel.app
- **API publicada:** https://mercado-viva-devoluciones.onrender.com
- **Documentación interactiva de la API:** https://mercado-viva-devoluciones.onrender.com/docs

## Integrantes

| Nombre | Rol en el trabajo |
|---|---|
|Jhair Andres Santamaria Arias | Definición del proceso, arquitectura, desarrollo y despliegue |

---

## 1. El proceso seleccionado

**Problema.** Cuando un cliente compra en la web o la app y quiere devolver el producto
en una tienda física, el asesor no tiene forma de ver el pedido digital. El cliente debe
mostrar correos o capturas, el asesor decide a criterio propio y la devolución queda
registrada solo en el punto de venta de esa tienda. El resultado son tiempos de atención
largos, decisiones distintas entre tiendas y ninguna trazabilidad.

**Actores.**

| Actor | Rol |
|---|---|
| Cliente digital | Solicita la devolución desde la web |
| Asesor de tienda | Verifica el producto físico y aprueba o rechaza |
| Administrador | Consulta el historial unificado |

**Inicio y fin.** Empieza cuando el cliente autenticado selecciona un pedido entregado y
crea la solicitud. Termina cuando el asesor registra su decisión en tienda y la solicitud
queda cerrada, con el reembolso autorizado y su historial de estados completo.

**Reglas del negocio.**

| # | Regla |
|---|---|
| R1 | Solo son devolvibles los pedidos en estado `ENTREGADO` |
| R2 | La solicitud debe crearse dentro de los 30 días calendario posteriores a la entrega |
| R3 | Se excluyen las categorías `PERECEDEROS` e `HIGIENE_PERSONAL` |
| R4 | La cantidad a devolver no puede superar la comprada menos la ya devuelta |
| R5 | Cada solicitud genera un código único con vigencia de 72 horas |
| R6 | Solo un usuario con rol `ASESOR` puede aprobar o rechazar |
| R7 | Toda transición se registra con usuario, fecha y motivo; los estados no retroceden |
| R8 | El correo identifica la cuenta; la contraseña exige 8 caracteres con letra y número |
| R9 | El rol se asigna en el servidor: el registro público solo crea cuentas `CLIENTE` |

**Restricciones del caso.**

1. No hay integración con la pasarela de pagos ni con el ERP. El MVP deja el reembolso
   en estado *autorizado* y expone el monto calculado, pero no mueve dinero.
2. El asesor trabaja en un equipo compartido con conectividad intermitente. De ahí la
   interfaz web sin instalación, la sesión corta que se borra al cerrar el navegador y
   las operaciones que no se duplican al reintentarlas.

**Objetivo medible.** Atender una devolución en tienda en menos de 5 minutos, con el
100 % de las solicitudes trazables mediante su historial de estados.

**Estados de la solicitud.**

```
                    ┌──────────► APROBADA   (cierre con reembolso autorizado)
PENDIENTE_VALIDACION├──────────► RECHAZADA  (cierre con motivo)
                    └──────────► EXPIRADA   (código vencido a las 72 h)
```

Los tres estados de la derecha son finales. Ninguna transición sale de ellos.

---

## 2. Tecnologías

| Capa | Tecnología | Por qué |
|---|---|---|
| Frontend | HTML5, CSS3, JavaScript ES6 | Sin compilación ni dependencias; se publica tal cual |
| Backend | Python 3.12 + FastAPI + Uvicorn | Valida la entrada automáticamente y genera documentación interactiva |
| Persistencia | PostgreSQL (Neon) | El flujo exige transacciones e integridad referencial |
| ORM | SQLAlchemy 2.0 | Aísla la lógica de negocio del motor de base de datos |
| Autenticación | JWT (python-jose) + bcrypt (passlib) | Sin estado en el servidor, con control por rol |
| Publicación | Vercel (frontend) y Render (backend) | Capa gratuita, HTTPS automático, despliegue desde GitHub |

Todas las herramientas son de código abierto.

**Comunicación.** El frontend habla con el backend por HTTPS usando REST sobre JSON, con
el token JWT en la cabecera `Authorization`. El backend habla con PostgreSQL por TCP
cifrado con TLS.

---

## 3. Arquitectura

```
Cliente digital ─┐
Asesor de tienda ─┼─► Frontend (Vercel) ─── HTTPS/JSON + JWT ──► Backend (Render) ─── SQL/TLS ──► PostgreSQL (Neon)
Administrador ───┘     HTML · CSS · JS                            FastAPI · Python
```

El backend es un **monolito modular**: se despliega como una sola unidad, pero por dentro
está separado en capas que no se saltan entre sí.

| Módulo | Responsabilidad |
|---|---|
| `app/routers/` | Exponen los endpoints REST y validan la entrada |
| `app/security.py` | Emite y valida los JWT; controla el acceso por rol |
| `app/reglas.py` | Las nueve reglas del negocio. **Sin dependencias externas** |
| `app/services/devoluciones.py` | Máquina de estados y orquestación del flujo |
| `app/models.py` | Las seis tablas |

`app/reglas.py` no importa FastAPI ni SQLAlchemy. Esa restricción es deliberada: permite
probar las reglas del negocio sin levantar la base de datos ni el servidor, que es lo que
exige el requisito no funcional RNF-03.

`app/muestras.py` simula el Sistema de Pedidos externo que aparece en el diagrama de
arquitectura. Cuando un cliente se registra, se le genera un historial de compras como si
llegara de la plataforma. En producción este módulo desaparece y los pedidos llegan por
integración.

**Mecanismos de seguridad.** HTTPS de extremo a extremo · JWT con expiración de 30 minutos ·
contraseñas con hash bcrypt · autorización por rol en cada endpoint · validación de toda la
entrada con Pydantic · CORS restringido al dominio del frontend · secretos en variables de
entorno, fuera del repositorio · neutralización del texto del usuario antes de mostrarlo
en pantalla.

---

## 4. Ejecutar el proyecto en local

Requisitos: Python 3.11 o superior. No hace falta instalar PostgreSQL: en local se usa
SQLite, que viene incluido con Python.

### Backend

```bash
cd backend

# 1. Entorno virtual
python -m venv .venv
source .venv/bin/activate          # en Windows:  .venv\Scripts\activate

# 2. Dependencias
pip install -r requirements.txt

# 3. Variables de entorno
cp .env.example .env               # en Windows:  copy .env.example .env

# 4. Datos de demostración
python -m app.seed

# 5. Servidor
uvicorn app.main:app --reload
```

La API queda en `http://127.0.0.1:8000` y la documentación interactiva en
`http://127.0.0.1:8000/docs`.

### Frontend

En otra terminal:

```bash
cd frontend
python -m http.server 5500
```

Abra `http://127.0.0.1:5500`. No abra los archivos con doble clic: el navegador bloquea
las peticiones desde `file://`.

### Cuentas

Cualquiera puede **crear una cuenta de cliente** desde la propia aplicación. Al
registrarse recibe un historial de compras simulado, porque en el MVP el
Sistema de Pedidos es un actor externo que no está integrado.

Las cuentas internas (`ASESOR` y `ADMIN`) **no se crean desde el formulario
público**. Se cargan con `python -m app.seed` y en producción las crearía el
área de operaciones. Esta separación es deliberada: si el registro permitiera
elegir el rol, cualquiera podría aprobar sus propias devoluciones.

Las cuentas de demostración que carga el `seed` están documentadas en
`app/seed.py`. No se muestran en la interfaz.

---

## 5. Pruebas

```bash
cd backend
pytest
```

Son 25 pruebas en dos archivos:

- **`tests/test_reglas.py`** — pruebas unitarias de las siete reglas. No abren base de
  datos ni servidor.
- **`tests/test_api.py`** — pruebas de integración que recorren la API completa.

Cuatro de ellas son casos excepcionales, que es lo que pide el taller:

| Caso | Respuesta esperada |
|---|---|
| Devolver más unidades de las compradas | 422 con la regla R4 |
| Devolver un producto perecedero | 422 con la regla R3 |
| Consultar un código vencido | 410, y la solicitud queda `EXPIRADA` |
| Aprobar dos veces la misma solicitud | 409, y el estado no cambia |
| Registrarse con un correo ya existente | 409, y no se crea un segundo usuario |
| Registrarse con contraseña débil | 422 con la regla R8 |
| Intentar registrarse como `ASESOR` | 201, pero la cuenta queda como `CLIENTE` |

Cada una verifica además que la operación fallida no dejó registros a medias en la base
de datos.

---

## 6. Endpoints

| Método | Ruta | Rol | Historia |
|---|---|---|---|
| `POST` | `/api/auth/registro` | — | Registro de clientes |
| `POST` | `/api/auth/login` | — | Autenticación |
| `GET` | `/api/auth/me` | cualquiera | Perfil |
| `GET` | `/api/pedidos/elegibles` | CLIENTE | HU-01 |
| `POST` | `/api/devoluciones` | CLIENTE | HU-02, HU-03 |
| `GET` | `/api/devoluciones/mias` | CLIENTE | Consulta propia |
| `GET` | `/api/devoluciones/codigo/{codigo}` | ASESOR | HU-04 |
| `POST` | `/api/devoluciones/{codigo}/decision` | ASESOR | HU-05 |
| `GET` | `/api/devoluciones` | ADMIN, ASESOR | Historial unificado |
| `GET` | `/api/health` | — | Estado del servicio |

**Formato de los errores.** Todos los errores del negocio responden con la misma
estructura, de modo que el frontend nunca tiene que interpretar códigos a mano:

```json
{
  "tipo": "regla_incumplida",
  "mensaje": "Cantidad superior a la disponible para devolucion...",
  "regla": "R4"
}
```

---

## 7. Estructura del repositorio

```
.
├── backend/
│   ├── app/
│   │   ├── reglas.py            ← las siete reglas, sin dependencias externas
│   │   ├── models.py            ← las seis tablas
│   │   ├── schemas.py           ← validación de entrada y salida
│   │   ├── security.py          ← JWT, bcrypt y control por rol
│   │   ├── errors.py            ← excepciones de dominio con su código HTTP
│   │   ├── main.py              ← aplicación, CORS y manejo de errores
│   │   ├── seed.py              ← datos de demostración
│   │   ├── routers/             ← auth, pedidos, devoluciones
│   │   └── services/            ← máquina de estados
│   ├── tests/                   ← 25 pruebas
│   └── requirements.txt
├── frontend/
│   ├── index.html               ← entrada
│   ├── cliente.html             ← portal del cliente
│   ├── tienda.html              ← módulo de tienda
│   ├── historial.html           ← historial unificado
│   ├── css/estilo.css
│   └── js/                      ← config, sesión, api y una pantalla por archivo
├── diagramas/
│   └── MercadoVIVA_Devoluciones.drawio
├── DESPLIEGUE.md
└── README.md
```

---

## 8. Alcance

**Incluido:** el flujo completo de la devolución, las siete reglas del negocio, la
autenticación con tres roles, la trazabilidad de estados y el historial unificado.

**Fuera del alcance, por decisión explícita:** la ejecución del reembolso a través de una
pasarela de pagos y la integración con el ERP. El MVP calcula el monto y lo deja
autorizado; la transferencia del dinero corresponde a una fase posterior.

---

```
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⡴⠖⠛⠓⠲⣤⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣸⣏⣀⣀⣀⣀⠀⠘⣿⡄⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢠⡿⠋⠉⠀⠈⠉⠻⣄⢹⣇⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⢧⣀⣀⡀⢀⣀⣤⣿⣿⠟⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠸⣿⣉⠉⣉⢉⣠⣾⠟⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣤⣶⣿⣿⣿⣿⣿⡿⠛⠳⣆⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⣀⣀⡠⠴⢿⣿⠋⠉⣹⠻⢿⣿⣿⣤⣴⣿⡆⠀⠀⠀⠀⠀⠀⠀
⠀⡀⠀⠀⢀⣀⣠⡾⠛⠋⠀⢀⡞⠀⠀⠀⠛⠀⠀⢹⡟⠻⣿⣿⣧⣄⡀⠀⣶⣤⣤⠀
⢠⣿⣷⣿⣿⠟⣛⣇⠀⠀⠀⣈⡷⣄⡀⠀⠀⠀⣠⣾⡟⠉⠉⠉⠉⢉⣿⣿⣿⣿⣿⡆
⢸⣿⣿⣿⠛⠁⠈⠙⢷⣦⠀⠀⠀⠀⠀⠈⢉⠋⢁⣼⣏⣡⣤⣤⢐⣺⣿⣿⣿⣿⠟⠁
⠀⠙⠿⣿⣷⢤⣀⡀⢸⢿⠀⠀⠀⠀⠒⣄⠈⢡⣾⣉⡤⠚⣩⢴⣿⣿⣿⣿⠿⠋⠀⠀
⠀⠀⠀⠙⢿⣷⣈⡙⠻⢿⣧⠀⠀⠀⠀⠸⡀⠈⠻⣯⡴⠋⣠⣾⡿⠟⠋⠁⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠙⢷⣿⢶⣤⣿⠈⠁⠀⠀⠀⠳⡄⠀⠙⢻⣿⡟⠁⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠽⣿⣽⣿⡀⠀⠀⠀⠀⠀⠿⣤⣴⣿⣿⣿⣦⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠈⠻⣿⣷⡄⠀⠀⢀⣤⣾⣿⣿⡿⠛⠛⠻⣷⡀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠙⣿⣿⣶⣿⣿⣿⣿⣿⣿⡿⠀⠀⠀⠘⣷⡀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢠⣿⣿⣿⣿⡇⣸⣿⡿⢻⡇⠀⠀⠀⠀⢹⡇⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⢠⣿⠿⠀⠈⠻⣷⣿⣿⡇⠈⠁⠀⠀⠀⢀⣾⡇⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⢠⡟⠁⠀⠀⠀⠀⣿⣿⣿⣷⠀⠀⢀⣤⣶⣿⣿⠇⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⣠⣿⡰⠀⠀⠀⣠⣾⣿⣿⣿⣿⣷⣿⣿⣿⣿⣿⡿⠀⠀⠀⠀⠀⠀
```