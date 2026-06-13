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
        app.config['BANNERS_FOLDER'],
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
    from .controllers.banner_controller import banner_bp
    from .controllers.grupo_controller import grupo_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(pdf_bp, url_prefix='/pdf')
    app.register_blueprint(carton_bp, url_prefix='/cartones')
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(banner_bp, url_prefix='/api/banners')
    app.register_blueprint(grupo_bp, url_prefix='/api/grupos')

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
        if 'grupo_id' not in cartones_cols:
            conn.execute(text("ALTER TABLE cartones ADD COLUMN grupo_id INTEGER"))
            conn.commit()
        if 'subido_por' not in pdfs_cols:
            conn.execute(text("ALTER TABLE pdfs_procesados ADD COLUMN subido_por INTEGER"))
            conn.commit()

        try:
            users_cols = [c['name'] for c in inspector.get_columns('users')]
            if 'grupo_id' not in users_cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN grupo_id INTEGER"))
                conn.commit()
        except Exception:
            pass

        # Migrar unique(numero) → unique(numero, grupo_id) si aún no se hizo
        try:
            indexes = inspector.get_indexes('cartones')
            has_composite = any(
                idx.get('name') == 'uq_carton_numero_grupo'
                for idx in indexes
            )
            if not has_composite:
                _migrar_cartones_unique_compuesta(conn)
        except Exception as e:
            print(f'[BINGO] AVISO migracion unique cartones: {e}', flush=True)


def _migrar_cartones_unique_compuesta(conn):
    """Recrea la tabla cartones para cambiar UNIQUE(numero) → UNIQUE(numero, grupo_id)."""
    from sqlalchemy import text
    conn.execute(text("PRAGMA foreign_keys=OFF"))
    conn.execute(text("""
        CREATE TABLE cartones_v2 (
            id          INTEGER NOT NULL PRIMARY KEY,
            numero      VARCHAR(20) NOT NULL,
            pdf_id      INTEGER NOT NULL,
            pagina_origen INTEGER NOT NULL,
            ruta_imagen VARCHAR(500) NOT NULL,
            vendedor_id INTEGER,
            grupo_id    INTEGER,
            estado      VARCHAR(20) NOT NULL DEFAULT 'disponible',
            comprador   VARCHAR(200),
            telefono_comprador VARCHAR(50),
            fecha_venta DATETIME,
            precio      NUMERIC(10, 2),
            notas       TEXT,
            fecha_creacion     DATETIME,
            fecha_actualizacion DATETIME,
            UNIQUE (numero, grupo_id)
        )
    """))
    conn.execute(text("INSERT INTO cartones_v2 SELECT * FROM cartones"))
    conn.execute(text("DROP TABLE cartones"))
    conn.execute(text("ALTER TABLE cartones_v2 RENAME TO cartones"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_cartones_numero ON cartones (numero)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_cartones_estado ON cartones (estado)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_cartones_vendedor_id ON cartones (vendedor_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_cartones_grupo_id ON cartones (grupo_id)"))
    conn.execute(text("PRAGMA foreign_keys=ON"))
    conn.commit()
    print('[BINGO] Migración OK: unique(numero) → unique(numero, grupo_id)', flush=True)


def _crear_admin_inicial():
    """Garantiza que el usuario admin existe y tiene la contraseña correcta usando SQL directo."""
    import os
    from werkzeug.security import generate_password_hash
    from sqlalchemy import text
    password = os.environ.get('ADMIN_PASSWORD', 'admin1234')
    password_hash = generate_password_hash(password)
    try:
        with db.engine.connect() as conn:
            existe = conn.execute(text("SELECT id FROM users WHERE username='admin'")).fetchone()
            if existe:
                conn.execute(text(
                    "UPDATE users SET password_hash=:ph, activo=1, rol='admin' WHERE username='admin'"
                ), {'ph': password_hash})
                print('[BINGO] Admin actualizado OK', flush=True)
            else:
                conn.execute(text(
                    "INSERT INTO users (username, password_hash, rol, activo) VALUES ('admin', :ph, 'admin', 1)"
                ), {'ph': password_hash})
                print('[BINGO] Admin creado OK', flush=True)
            conn.commit()
    except Exception as e:
        print(f'[BINGO] ERROR admin init: {e}', flush=True)
