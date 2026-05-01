## Orbidi FastAPI Tickets App

App FastAPI lista para correr en local con:

- **SSO Google** (`fastapi-sso`) + **sesión en cookie** (`SessionMiddleware`)
- **PostgreSQL** con **SQLAlchemy async** + Alembic
- **Tickets / comentarios / adjuntos** (REST API)
- **Notificaciones** persistentes (REST API)
- **Static files** en `static/`
- **Storage local** en `./data/uploads`

---

### Requisitos

Opción recomendada (más simple):

- Docker Desktop (incluye `docker compose`)

Opción sin Docker (avanzada):

- Python >= 3.11
- Postgres corriendo localmente
- `uv` instalado (recomendado) o `pip`

---

### Variables de entorno

Crea un archivo `.env` en la raíz del repo (puedes copiarlo desde `.env.example`).

```bash
cp .env.example .env
```

Mínimo recomendado para desarrollo (funciona con `docker compose` por defecto):

```env
ENVIRONMENT=dev
BASE_URL=http://localhost:8000

# Sesiones (cookie firmada). Cambiar en prod.
SECRET_KEY=change-me

# Infra (Docker compose defaults)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/app
RABBITMQ_URL=amqp://guest:guest@localhost:5672/

# Google OAuth (opcional: si no lo configuras, /auth/login fallará)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/callback
```

Notas:

- En Google Cloud Console, agrega el callback `http://localhost:8000/auth/callback` como redirect URI autorizado.
- Si no configuras Google, puedes seguir usando el API de tickets si creas usuarios en DB manualmente o si adaptas la auth (en este proyecto, crear tickets/comentarios requiere sesión).

---

### Levantar en local con Docker Compose

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

### Ejecutar migraciones (Alembic)

El proyecto utiliza **Alembic configurado de manera asíncrona** para funcionar correctamente con el driver `asyncpg`.

- La configuración está en `alembic/env.py` y toma la URL desde `app.core.config.get_settings()` (variable `DATABASE_URL`).
- Las versiones de las migraciones se encuentran en `alembic/versions/` y deben estar versionadas en Git.

Aplicar migraciones:

```bash
docker compose exec app uv run alembic upgrade head
```

Autogenerar nueva migración (si cambias los modelos):

```bash
docker compose exec app uv run alembic revision --autogenerate -m "descripcion"
```

#### ¿Cómo resetear la DB y empezar de cero?

Si necesitas borrar todos los datos y regenerar las migraciones desde cero:

1. Borra los volúmenes de Docker: `docker compose down -v`
2. Borra los archivos en `alembic/versions/` (excepto `__init__.py`).
3. Levanta los servicios: `docker compose up -d`
4. Genera la migración inicial: `docker compose exec app uv run alembic revision --autogenerate -m "initial"`
5. Aplica la migración: `docker compose exec app uv run alembic upgrade head`

---

### Probar la app (rápido)

Web:

- Abre `http://localhost:8000`

SSO Google:

- `GET /auth/login`
- `GET /auth/callback`
- `POST /auth/logout`

---

### REST API: Tickets / Comentarios / Adjuntos

Base path: `/api/tickets`

Tickets:

- `GET /api/tickets`
- `POST /api/tickets` (requiere sesión, **JSON**)
- `GET /api/tickets/{ticket_id}`
- `PATCH /api/tickets/{ticket_id}`
- `DELETE /api/tickets/{ticket_id}`

Comentarios:

- `GET /api/tickets/{ticket_id}/comments`
- `POST /api/tickets/{ticket_id}/comments` (requiere sesión)
- `DELETE /api/tickets/comments/{comment_id}`

Adjuntos:

- `GET /api/tickets/{ticket_id}/attachments`
- `POST /api/tickets/{ticket_id}/attachments` (requiere sesión, **multipart/form-data**, múltiples archivos, max 10MB c/u)
- `DELETE /api/tickets/attachments/{attachment_id}`

Estados soportados del ticket:

- `Abierto`, `En progreso`, `En revisión`, `Cerrado`

---

### Estructura del proyecto

- `app/main.py`: crea la app FastAPI, middleware de sesión, static, routers y lifespan
- `app/auth/*`: SSO Google + helpers de sesión
- `app/db/*`: SQLAlchemy async
- `app/*/models.py`: modelos ORM (`User`, `Ticket`, `Comment`, `Notification`, etc.)
- `app/tickets/*`: REST API (schemas, repository, routes, storage)
- `alembic/`: migraciones
- `static/`: assets estáticos

---

### Comandos útiles

Ver logs:

```bash
docker compose logs -f app
```

Reiniciar con volúmenes limpios (borra datos de Postgres):

```bash
docker compose down -v
```

---

### Notas de Desarrollo

#### Uso de `from __future__ import annotations`

A lo largo del proyecto (especialmente en modelos y schemas) se usa `from __future__ import annotations` para:

1. Evitar problemas de forward references en tipado (relaciones entre modelos).
2. Usar sintaxis moderna de tipos (como `list[str]` o `int | None`).
