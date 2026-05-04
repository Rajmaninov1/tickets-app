# Orbidi FastAPI Tickets App

App de tickets para prueba ténica de Orbidi

## Decisiones técnicas

- Uso de **FastAPI** para el backend
- **SSO Google** (`fastapi-sso`) + **sesión en cookie** (`SessionMiddleware`)
- **PostgreSQL** con **SQLAlchemy async** + Alembic
- **Tickets / comentarios / adjuntos** (REST API)
- Notificaciones con RabbitMQ + WebSockets: Implementación de un flujo asíncrono para notificaciones, permitiendo un sistema reactivo y desacoplado de la lógica principal del ticket.
- **Static files** en `static/`
- **Storage local** en `./data/uploads`
- Frontend con **Vue**
- Organización de carpetas según entidades del dominio
- **docker compose** para levantar los servicios en local
- **Manejo Desacoplado de Adjuntos**: Separación de la creación de tickets de la subida de archivos para un manejo más limpio de payloads Multipart.
- Se optó por una arquitectura por dominios priorizando la velocidad de desarrollo, manteniendo una separación clara entre controladores y repositorios, lo que facilitaría una futura transición a Clean Architecture si la aplicación crece en complejidad.
- El frontend se desarrolló como una Single Page Application (SPA) reactiva con Vue, priorizando la funcionalidad y la integración con la API sobre una arquitectura compleja de componentes, dado que el foco principal de la prueba es el backend. Hecha con "vibe coding", pues no tengo experiencia en frontend.

## Herramientas de IA usadas

- **Antigravity** para generar y analizar código y corregir errores
- **Cursor** para generar código y corregir errores (primera vez que lo usaba pero lo intenté por la llamada que tuve con July Vanessa donde mencionó que la usan en su equipo)

---

## Requisitos

- Docker Desktop (incluye `docker compose`)

---

## Partes completadas

Todas las partes principales de la aplicación están completas, incluyendo:

- Autenticación SSO Google.
- CRUD completo de Tickets con comentarios y adjuntos.
- Tablero Kanban interactivo con Drag & Drop.
- Vista de lista con ordenamiento dinámico por múltiples columnas.
- Sistema de notificaciones en tiempo real (RabbitMQ + WebSockets).
- Gestión de estados y asignaciones con búsqueda reactiva de usuarios.
- Descarga segura de archivos adjuntos.

*Nota: Los tests unitarios y el bonus de agentes de IA quedaron pendientes.*

## Variables de entorno

Crea un archivo `.env` en la raíz del repo (puedes copiarlo desde `.env.example`).

```bash
cp .env.example .env
```

### Campos obligatorios

Para que la aplicación funcione correctamente (especialmente el login), **debes configurar las siguientes variables**:

1. **Google OAuth (Obligatorio para el Login):**
   - `GOOGLE_CLIENT_ID`: ID de cliente obtenido en Google Cloud Console.
   - `GOOGLE_CLIENT_SECRET`: Secreto de cliente obtenido en Google Cloud Console.
   - `GOOGLE_REDIRECT_URI`: Debe ser `http://localhost:8000/auth/callback` (o el puerto que uses).

2. **Seguridad:**
   - `SECRET_KEY`: Una cadena aleatoria para firmar las cookies de sesión.

3. **Base de Datos y Broker:**
   - Las variables `POSTGRES_*`, `DATABASE_URL` y `RABBITMQ_URL` ya vienen con valores por defecto en el `.env.example` para funcionar con lo configurado en `docker compose`.

Notas:

- En Google Cloud Console, agrega el callback `http://localhost:8000/auth/callback` como redirect URI autorizado.
- Si no configuras Google, puedes seguir usando el API de tickets si creas usuarios en DB manualmente o si adaptas la auth (en este proyecto, crear tickets/comentarios requiere sesión).

---

## Levantar en local con Docker Compose

1) Levanta los servicios:

```bash
docker compose up --build
```

1) Migraciones (Alembic)

La imagen de la app ejecuta `alembic upgrade head` **automáticamente al iniciar** (ver `Dockerfile`), así que en el flujo normal con `docker compose up` no necesitas correr nada manualmente.

Si quieres ejecutarlas a mano (por ejemplo, después de crear una nueva revisión), puedes hacerlo en otra terminal:

```bash
docker compose exec app uv run alembic upgrade head
```

Servicios:

- App: `http://localhost:8000`
- RabbitMQ management: `http://localhost:15672` (user/pass: `guest` / `guest`)
- Postgres: `localhost:5432` (user/pass: `postgres` / `postgres`, db: `app`)

---

## Ejecutar migraciones (Alembic)

El proyecto utiliza **Alembic configurado de manera asíncrona** para funcionar correctamente con el driver `asyncpg`.

- La configuración está en `alembic/env.py` y toma la URL desde `app.core.config.get_settings()` (variable `DATABASE_URL`).
- Las versiones de las migraciones se encuentran en `alembic/versions/` y deben estar versionadas en Git.

Autogenerar nueva migración (si cambias los modelos):

```bash
docker compose exec app uv run alembic revision --autogenerate -m "descripcion"
```

### ¿Cómo resetear la DB y empezar de cero?

Si necesitas borrar todos los datos y regenerar las migraciones desde cero:

1. Borra los volúmenes de Docker: `docker compose down -v`
2. Borra los archivos en `alembic/versions/` (excepto `__init__.py`).
3. Levanta los servicios: `docker compose up -d`
4. Genera la migración inicial: `docker compose exec app uv run alembic revision --autogenerate -m "initial"`
5. Aplica la migración: `docker compose exec app uv run alembic upgrade head`

---

## Probar la app

Web:

- Abre `http://localhost:8000`

Backend:

- Abre `http://localhost:8000/docs`

---

## Notas de Desarrollo

### Uso de `from __future__ import annotations`

A lo largo del proyecto (especialmente en modelos y schemas) se usa `from __future__ import annotations` para:

1. Evitar problemas de forward references en tipado (relaciones entre modelos).
2. Usar sintaxis moderna de tipos (como `list[str]` o `int | None`).
