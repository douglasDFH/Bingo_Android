"""Gestión de permisos por rol (solo admin puede modificar)."""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from ..models import db
from ..models.permiso import PermisoRol, PERMISOS_DISPONIBLES
from ..models.user import User

permisos_bp = Blueprint('permisos', __name__)


@permisos_bp.route('')
@jwt_required()
def get_permisos():
    """Devuelve los permisos configurados para el rol vendedor."""
    _, rol = int(get_jwt_identity()), get_jwt().get('rol', '')
    if rol != User.ROL_ADMIN:
        return jsonify({'error': 'Solo admin'}), 403
    permisos = PermisoRol.get_for_rol('vendedor')
    return jsonify({
        'rol': 'vendedor',
        'permisos': permisos,
        'labels': PERMISOS_DISPONIBLES,
    })


@permisos_bp.route('/<permiso>', methods=['PUT'])
@jwt_required()
def toggle_permiso(permiso):
    """Activa o desactiva un permiso del rol vendedor."""
    _, rol = int(get_jwt_identity()), get_jwt().get('rol', '')
    if rol != User.ROL_ADMIN:
        return jsonify({'error': 'Solo admin'}), 403
    if permiso not in PERMISOS_DISPONIBLES:
        return jsonify({'error': 'Permiso no válido'}), 400

    data = request.get_json() or {}
    habilitado = bool(data.get('habilitado', False))

    row = PermisoRol.query.filter_by(rol='vendedor', permiso=permiso).first()
    if row:
        row.habilitado = habilitado
    else:
        db.session.add(PermisoRol(rol='vendedor', permiso=permiso, habilitado=habilitado))
    db.session.commit()
    return jsonify({'ok': True, 'permiso': permiso, 'habilitado': habilitado})
