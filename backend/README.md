# Bingo Imperial — Sistema MVC

Aplicación web en Python (Flask) con arquitectura MVC y base de datos SQLite.
Replica el flujo:
PDF de cartones de bingo → extrae el número del pie de cada página → genera
una imagen JPG por cartón → registra todo en la base de datos → permite
listar, buscar, vender, reservar y liberar cartones desde el navegador.

## Estructura del proyecto

```
bingo_app/
├── app/
│   ├── __init__.py            # Factory de Flask (registra DB y blueprints)
│   ├── config.py              # Configuración (DB, carpetas, DPI, formato)
│   ├── models/                # (M) Modelos SQLAlchemy
│   │   ├── pdf_procesado.py
│   │   └── carton.py
│   ├── controllers/           # (C) Controladores / rutas
│   │   ├── main_controller.py
│   │   ├── pdf_controller.py
│   │   └── carton_controller.py
│   ├── services/              # Lógica de negocio reusable
│   │   └── pdf_processor.py   # Convierte PDF a JPGs + extrae números
│   ├── templates/             # (V) Vistas Jinja
│   │   ├── base.html
│   │   ├── index.html
│   │   ├── pdfs/
│   │   └── cartones/
│   └── static/css/style.css
├── instance/bingo.db          # Base de datos SQLite (se crea sola)
├── uploads/                   # PDFs subidos (se crea sola)
├── imagenes_generadas/        # Imágenes JPG generadas (se crea sola)
├── requirements.txt
└── run.py                     # Punto de entrada
```

## Requisitos previos

1. **Python 3.10+**
2. **Poppler** (provee `pdftotext` y `pdftoppm`):
   - Windows: descargar https://github.com/oschwartz10612/poppler-windows/releases
     y agregar la carpeta `Library\bin` (o `bin`) al PATH del sistema.
     Alternativa con Chocolatey: `choco install poppler`
   - macOS: `brew install poppler`
   - Linux: `sudo apt install poppler-utils`

Verifica con:
```
pdftotext -v
pdftoppm -v
```

## Instalación

```bash
cd bingo_app
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

## Ejecutar

```bash
python run.py
```

Abre el navegador en **http://localhost:5000**.

La primera vez se crea automáticamente:
- el archivo `instance/bingo.db` con las tablas
- las carpetas `uploads/` e `imagenes_generadas/`

## Flujo de uso

1. **Dashboard** (`/`) — métricas generales.
2. **Subir PDF** (`/pdf/subir`) — selecciona el PDF de cartones; el sistema
   extrae el número del pie de cada página, genera una imagen por cartón
   y crea los registros en la base de datos.
3. **Cartones** (`/cartones`) — buscar por número o comprador, filtrar por
   estado, paginación.
4. **Detalle del cartón** (`/cartones/<id>`) — ver la imagen, marcar como
   vendido (con datos del comprador, precio, notas), reservar o liberar.
5. **API JSON** simple — `GET /cartones/api/buscar?q=6001` devuelve
   coincidencias en JSON, útil para integrar con otras herramientas.

## Arquitectura MVC

- **Model** — `app/models/` define las tablas con SQLAlchemy:
  `PDFProcesado` (un registro por PDF) y `Carton` (un registro por página).
- **View** — `app/templates/` con Jinja2 + CSS.
- **Controller** — `app/controllers/` con Blueprints de Flask. Cada
  controlador agrupa rutas relacionadas (PDFs, cartones, dashboard).
- **Service** — `app/services/pdf_processor.py` encapsula la lógica de
  procesamiento, separada de las rutas para poder reutilizarla (p. ej. en
  scripts batch o tareas programadas).

## Base de datos

SQLite, archivo único en `instance/bingo.db`.

Tablas:

**`pdfs_procesados`**
| campo | tipo | descripción |
|-------|------|-------------|
| id | int | PK |
| nombre_archivo | str | nombre original |
| ruta_archivo | str | ruta en disco |
| fecha_procesado | datetime | |
| total_paginas, paginas_ok, paginas_error | int | |
| carpeta_imagenes | str | |
| dpi | int | resolución usada |
| estado | str | pendiente / procesando / completado / error |
| mensaje_error | text | |

**`cartones`**
| campo | tipo | descripción |
|-------|------|-------------|
| id | int | PK |
| numero | str | único, indexado (ej. "6001") |
| pdf_id | int | FK a pdfs_procesados |
| pagina_origen | int | nº de página en el PDF |
| ruta_imagen | str | path absoluto |
| estado | str | disponible / vendido / reservado |
| comprador, telefono_comprador | str | |
| precio | decimal | |
| fecha_venta, fecha_creacion, fecha_actualizacion | datetime | |
| notas | text | |

## Personalización rápida

- Cambiar DPI o formato → editar `app/config.py` (`DPI_IMAGENES`, `FORMATO_IMAGEN`).
- Cambiar a MySQL/PostgreSQL → cambiar `SQLALCHEMY_DATABASE_URI` en `config.py`
  (instalar el driver correspondiente, ej. `pymysql` o `psycopg2`).

## Notas

- El procesamiento del PDF es **síncrono** al subir el archivo. Para PDFs muy
  grandes (>10k páginas) conviene moverlo a una tarea en background con Celery o
  RQ. La función `procesar` acepta un callback de progreso para integrarlo.
- Las imágenes se guardan fuera de `static/` y se sirven mediante la ruta
  `/cartones/<id>/imagen`, que también valida que el cartón exista en la DB.
