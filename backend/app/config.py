"""Configuración central de la aplicación."""
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


class Config:
    SECRET_KEY     = os.environ.get('SECRET_KEY', 'cambia-esto-en-produccion')
    JWT_SECRET_KEY = os.environ.get('SECRET_KEY', 'cambia-esto-en-produccion')
    JWT_ACCESS_TOKEN_EXPIRES = 60 * 60 * 24 * 30  # 30 días

    SQLALCHEMY_DATABASE_URI = (
        'sqlite:///' + os.path.join(BASE_DIR, 'instance', 'bingo.db')
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # SQLite: esperar hasta 30s si está bloqueada por otro hilo/proceso
    SQLALCHEMY_ENGINE_OPTIONS = {
        'connect_args': {'timeout': 30},
    }

    # Carpetas
    UPLOAD_FOLDER   = os.path.join(BASE_DIR, 'uploads')
    IMAGENES_FOLDER = os.path.join(BASE_DIR, 'imagenes_generadas')
    BANNERS_FOLDER  = os.path.join(BASE_DIR, 'uploads', 'banners')

    # Límite de subida 200 MB
    MAX_CONTENT_LENGTH = 200 * 1024 * 1024

    # Parámetros de procesamiento
    DPI_IMAGENES   = 150   # 150 dpi: buena calidad sin archivos enormes
    FORMATO_IMAGEN = 'jpeg'
