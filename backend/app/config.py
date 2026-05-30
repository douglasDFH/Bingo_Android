"""Configuración central de la aplicación."""
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


class Config:
    SECRET_KEY     = os.environ.get('SECRET_KEY', 'cambia-esto-en-produccion')
    JWT_SECRET_KEY = os.environ.get('SECRET_KEY', 'cambia-esto-en-produccion')
    JWT_ACCESS_TOKEN_EXPIRES = 60 * 60 * 24 * 30  # 30 días

    # SQLite local en la carpeta instance/
    SQLALCHEMY_DATABASE_URI = (
        'sqlite:///' + os.path.join(BASE_DIR, 'instance', 'bingo.db')
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Carpetas
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    IMAGENES_FOLDER = os.path.join(BASE_DIR, 'imagenes_generadas')

    # Límite de subida 200 MB (ajustable)
    MAX_CONTENT_LENGTH = 200 * 1024 * 1024

    # Parámetros de procesamiento
    DPI_IMAGENES = 100
    FORMATO_IMAGEN = 'jpeg'  # 'jpeg' o 'png'
