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
    from sqlalchemy import text, inspect
    inspector = inspect(db.engine)

    try:
        cartones_cols = [c['name'] for c in inspector.get_columns('cartones')]
        pdfs_cols = [c['name'] for c in inspector.get_columns('pdfs_procesados')]
    except Exception:
        return

    with db.engine.connect() as conn:
        if 'vendedor_id' not in cartones_cols:
            conn.execute(text("ALTER TABLE cartones ADD COLUMN vendedor_id INTEGER"))
            conn.commit()
        if 'subido_por' not in pdfs_cols:
            conn.execute(text("ALTER TABLE pdfs_procesados ADD COLUMN subido_por INTEGER"))
            conn.commit()


def _crear_admin_inicial():
    """Garantiza que el usuario admin existe y tiene la contraseña correcta."""
    import os
    from .models.user import User
    try:
        password = os.environ.get('ADMIN_PASSWORD', 'admin1234')
        admin = User.query.filter_by(username='admin').first()
        if admin is None:
            admin = User(username='admin', rol=User.ROL_ADMIN)
            db.session.add(admin)
            print('[BINGO] Admin creado por primera vez', flush=True)
        else:
            print(f'[BINGO] Admin encontrado id={admin.id} activo={admin.activo}, actualizando password', flush=True)
        admin.set_password(password)
        admin.activo = True
        admin.rol = User.ROL_ADMIN
        db.session.commit()
        print('[BINGO] Admin listo OK - usuario=admin password=admin1234', flush=True)
    except Exception as e:
        db.session.rollback()
        print(f'[BINGO] ERROR al inicializar admin: {e}', flush=True)
