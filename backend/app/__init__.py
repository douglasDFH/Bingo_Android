"""Factory de la aplicación Flask."""
import os
from flask import Flask
from .models import db
from .config import Config


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    # Asegurar que existan las carpetas necesarias
    for folder in (
        app.config['UPLOAD_FOLDER'],
        app.config['IMAGENES_FOLDER'],
        app.instance_path,
    ):
        os.makedirs(folder, exist_ok=True)

    # Inicializar base de datos
    db.init_app(app)

    # Registrar blueprints (controladores)
    from .controllers.main_controller import main_bp
    from .controllers.pdf_controller import pdf_bp
    from .controllers.carton_controller import carton_bp
    from .controllers.api_controller import api_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(pdf_bp, url_prefix='/pdf')
    app.register_blueprint(carton_bp, url_prefix='/cartones')
    app.register_blueprint(api_bp, url_prefix='/api')

    # CORS para la app móvil (emulador usa 10.0.2.2)
    @app.after_request
    def add_cors(response):
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        return response

    # Crear tablas al iniciar
    with app.app_context():
        db.create_all()

    return app
