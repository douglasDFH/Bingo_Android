"""Factory de la aplicación Flask."""
import os
import traceback
from flask import Flask, jsonify
from flask_jwt_extended import JWTManager
from .models import db
from .config import Config


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    for folder in (
        app.config['UPLOAD_FOLDER'],
        app.config['IMAGENES_FOLDER'],
        app.instance_path,
    ):
        os.makedirs(folder, exist_ok=True)

    db.init_app(app)
    JWTManager(app)

    from .controllers.main_controller import main_bp
    from .controllers.pdf_controller import pdf_bp
    from .controllers.carton_controller import carton_bp
    from .controllers.api_controller import api_bp
    from .controllers.auth_controller import auth_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(pdf_bp, url_prefix='/pdf')
    app.register_blueprint(carton_bp, url_prefix='/cartones')
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(auth_bp, url_prefix='/api/auth')

    @app.after_request
    def add_cors(response):
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS, DELETE, PUT'
        return response

    @app.errorhandler(Exception)
    def handle_exception(e):
        tb = traceback.format_exc()
        app.logger.error(f"Unhandled exception: {e}\n{tb}")
        return jsonify({'error': str(e), 'trace': tb[-1000:]}), 500

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({'error': 'Ruta no encontrada', 'detail': str(e)}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({'error': 'Metodo no permitido', 'detail': str(e)}), 405

    with app.app_context():
        db.create_all()
        _migrar_columnas()
        _crear_admin_inicial()

    return app


def _migrar_columnas():
    """Agrega columnas nuevas a tablas SQLite existentes sin romper datos."""
    from sqlalchemy import text
    migraciones = [
        "ALTER TABLE cartones ADD COLUMN vendedor_id INTEGER REFERENCES users(id)",
        "ALTER TABLE pdfs_procesados ADD COLUMN subido_por INTEGER REFERENCES users(id)",
    ]
    with db.engine.connect() as conn:
        for sql in migraciones:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                pass  # Columna ya existe


def _crear_admin_inicial():
    """Crea el usuario admin por defecto si no existe ninguno."""
    from .models.user import User
    if User.query.count() == 0:
        admin = User(username='admin', rol=User.ROL_ADMIN)
        admin.set_password('admin1234')
        db.session.add(admin)
        db.session.commit()
