"""Autenticacion: login, me, usuarios (solo admin)."""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import (
    create_access_token, jwt_required, get_jwt_identity, get_jwt
)
from ..models import db
from ..models.user import User

auth_bp = Blueprint('auth', __name__)


def admin_required(fn):
    """Decorador que exige rol admin."""
    from functools import wraps
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        claims = get_jwt()
        if claims.get('rol') != User.ROL_ADMIN:
            return jsonify({'error': 'Se requiere rol admin'}), 403
        return fn(*args, **kwargs)
    return wrapper


@auth_bp.route('/debug-admin')
def debug_admin():
    """Endpoint temporal para verificar estado del admin."""
    users = User.query.all()
    return jsonify({
        'total_usuarios': len(users),
        'usuarios': [{'id': u.id, 'username': u.username, 'rol': u.rol, 'activo': u.activo} for u in users]
    })


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'error': 'Usuario y contraseña requeridos'}), 400

    user = User.query.filter_by(username=username).first()
    print(f'[BINGO] Login: username={username} existe={user is not None} activo={user.activo if user else None}', flush=True)
    if not user or not user.activo:
        return jsonify({'error': 'Credenciales incorrectas'}), 401
    if not user.check_password(password):
        print(f'[BINGO] Login FALLIDO: password incorrecto para {username}', flush=True)
        return jsonify({'error': 'Credenciales incorrectas'}), 401

    token = create_access_token(
        identity=str(user.id),
        additional_claims={'rol': user.rol, 'username': user.username}
    )
    return jsonify({'token': token, 'user': user.to_dict()})


@auth_bp.route('/me')
@jwt_required()
def me():
    user_id = get_jwt_identity()
    user = User.query.get_or_404(int(user_id))
    return jsonify(user.to_dict())


@auth_bp.route('/usuarios')
@admin_required
def listar_usuarios():
    usuarios = User.query.order_by(User.username).all()
    return jsonify([u.to_dict() for u in usuarios])


@auth_bp.route('/usuarios', methods=['POST'])
@admin_required
def crear_usuario():
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')
    rol = data.get('rol', User.ROL_VENDEDOR)

    if not username or not password:
        return jsonify({'error': 'Usuario y contraseña requeridos'}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'El usuario ya existe'}), 409

    user = User(username=username, rol=rol)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return jsonify(user.to_dict()), 201


@auth_bp.route('/usuarios/<int:user_id>', methods=['PUT'])
@admin_required
def actualizar_usuario(user_id):
    user = User.query.get_or_404(user_id)
    data = request.get_json() or {}

    if 'password' in data and data['password']:
        user.set_password(data['password'])
    if 'rol' in data and data['rol'] in (User.ROL_ADMIN, User.ROL_VENDEDOR):
        user.rol = data['rol']
    if 'activo' in data:
        if str(user_id) == get_jwt_identity() and not data['activo']:
            return jsonify({'error': 'No puedes desactivar tu propia cuenta'}), 400
        user.activo = bool(data['activo'])

    db.session.commit()
    return jsonify(user.to_dict())


@auth_bp.route('/usuarios/<int:user_id>', methods=['DELETE'])
@admin_required
def eliminar_usuario(user_id):
    user = User.query.get_or_404(user_id)
    if str(user_id) == get_jwt_identity():
        return jsonify({'error': 'No puedes eliminar tu propia cuenta'}), 400
    db.session.delete(user)
    db.session.commit()
    return jsonify({'ok': True})
