"""API CRUD de banners (headers personalizados para cartones)."""
import os
import uuid
from flask import Blueprint, jsonify, request, send_file, current_app
from flask_jwt_extended import jwt_required, get_jwt
from werkzeug.utils import secure_filename
from ..models import db
from ..models.banner import Banner
from ..models.user import User

banner_bp = Blueprint('banners', __name__)

_ALLOWED_EXT = {'jpeg', 'jpg', 'png'}


def _es_admin():
    return get_jwt().get('rol', '') == User.ROL_ADMIN


@banner_bp.before_request
@jwt_required()
def require_auth():
    pass


@banner_bp.route('', methods=['GET'])
def listar_banners():
    banners = Banner.query.filter_by(activo=True).order_by(Banner.nombre).all()
    return jsonify([b.to_dict() for b in banners])


@banner_bp.route('', methods=['POST'])
def crear_banner():
    if not _es_admin():
        return jsonify({'error': 'Solo admin'}), 403

    nombre = request.form.get('nombre', '').strip()
    if not nombre:
        return jsonify({'error': 'El nombre es requerido'}), 400

    if 'imagen' not in request.files:
        return jsonify({'error': 'Se requiere una imagen'}), 400

    archivo = request.files['imagen']
    if not archivo.filename:
        return jsonify({'error': 'Archivo sin nombre'}), 400

    ext = archivo.filename.rsplit('.', 1)[-1].lower() if '.' in archivo.filename else ''
    if ext not in _ALLOWED_EXT:
        return jsonify({'error': 'Solo se permiten imágenes JPEG o PNG'}), 400

    banners_folder = current_app.config['BANNERS_FOLDER']
    os.makedirs(banners_folder, exist_ok=True)

    nombre_archivo = f"{uuid.uuid4().hex}.{ext}"
    ruta = os.path.join(banners_folder, nombre_archivo)
    archivo.save(ruta)

    banner = Banner(nombre=nombre, ruta_imagen=ruta)
    db.session.add(banner)
    db.session.commit()

    print(f'[BINGO] Banner creado: id={banner.id} nombre={nombre}', flush=True)
    return jsonify(banner.to_dict()), 201


@banner_bp.route('/<int:banner_id>', methods=['PUT'])
def actualizar_banner(banner_id):
    if not _es_admin():
        return jsonify({'error': 'Solo admin'}), 403

    banner = Banner.query.get_or_404(banner_id)
    data = request.get_json() or {}

    nombre = data.get('nombre', '').strip()
    if not nombre:
        return jsonify({'error': 'El nombre no puede estar vacío'}), 400

    banner.nombre = nombre
    db.session.commit()
    return jsonify(banner.to_dict())


@banner_bp.route('/<int:banner_id>', methods=['DELETE'])
def eliminar_banner(banner_id):
    if not _es_admin():
        return jsonify({'error': 'Solo admin'}), 403

    banner = Banner.query.get_or_404(banner_id)
    ruta = banner.ruta_imagen

    db.session.delete(banner)
    db.session.commit()

    if ruta and os.path.isfile(ruta):
        os.remove(ruta)

    print(f'[BINGO] Banner eliminado: id={banner_id}', flush=True)
    return jsonify({'ok': True})


@banner_bp.route('/<int:banner_id>/imagen', methods=['GET'])
def imagen_banner(banner_id):
    banner = Banner.query.get_or_404(banner_id)
    if not os.path.isfile(banner.ruta_imagen):
        return jsonify({'error': 'Imagen no encontrada'}), 404
    return send_file(banner.ruta_imagen)
