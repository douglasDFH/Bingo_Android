"""Inicialización del paquete de modelos."""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# Importar modelos para que SQLAlchemy los registre
from .pdf_procesado import PDFProcesado  # noqa: E402,F401
from .carton import Carton  # noqa: E402,F401
from .user import User  # noqa: E402,F401
from .banner import Banner  # noqa: E402,F401
