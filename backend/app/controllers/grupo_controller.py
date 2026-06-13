"""API CRUD de grupos de bingo."""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt
from ..models import db
from ..models.grupo import Grupo
from ..models.user import User

grupo_bp = Blueprint('grupos', __name__)


def _es_admin():
    return get_jwt().get('rol', '') == User.ROL_ADMIN


@grupo_bp.before_request
@jwt_required()
def require_auth():
    pass


@grupo_bp.route('', methods=['GET'])
def listar_grupos():
    grupos = Grupo.query.filter_by(activo=True).order_by(Grupo.nombre).all()
    return jsonify([g.to_dict() for g in grupos])


@grupo_bp.route('', methods=['POST'])
def crear_grupo():
    if not _es_admin():
        return jsonify({'error': 'Solo admin'}), 403

    data = request.get_json() or {}
    nombre = data.get('nombre', '').strip()
    if not nombre:
        return jsonify({'error': 'El nombre es requerido'}), 400
    if Grupo.query.filter_by(nombre=nombre).first():
        return jsonify({'error': 'Ya existe un grupo con ese nombre'}), 409

    grupo = Grupo(nombre=nombre)
    db.session.add(grupo)
    db.session.commit()
    print(f'[BINGO] Grupo creado: id={grupo.id} nombre={nombre}', flush=True)
    return jsonify(grupo.to_dict()), 201


@grupo_bp.route('/<int:grupo_id>', methods=['PUT'])
def actualizar_grupo(grupo_id):
    if not _es_admin():
        return jsonify({'error': 'Solo admin'}), 403

    grupo = Grupo.query.get_or_404(grupo_id)
    data = request.get_json() or {}
    nombre = data.get('nombre', '').strip()
    if not nombre:
        return jsonify({'error': 'El nombre no puede estar vacío'}), 400

    existente = Grupo.query.filter_by(nombre=nombre).first()
    if existente and existente.id != grupo_id:
        return jsonify({'error': 'Ya existe un grupo con ese nombre'}), 409

    grupo.nombre = nombre
    db.session.commit()
    return jsonify(grupo.to_dict())


@grupo_bp.route('/<int:grupo_id>', methods=['DELETE'])
def eliminar_grupo(grupo_id):
    if not _es_admin():
        return jsonify({'error': 'Solo admin'}), 403

    grupo = Grupo.query.get_or_404(grupo_id)
    # Desasociar usuarios antes de eliminar
    User.query.filter_by(grupo_id=grupo_id).update({'grupo_id': None})
    db.session.delete(grupo)
    db.session.commit()
    print(f'[BINGO] Grupo eliminado: id={grupo_id}', flush=True)
    return jsonify({'ok': True})


@grupo_bp.route('/<int:grupo_id>/usuarios', methods=['GET'])
def usuarios_del_grupo(grupo_id):
    if not _es_admin():
        return jsonify({'error': 'Solo admin'}), 403

    Grupo.query.get_or_404(grupo_id)
    usuarios = (User.query
                .filter_by(grupo_id=grupo_id, activo=True)
                .order_by(User.username)
                .all())
    return jsonify([u.to_dict() for u in usuarios])
