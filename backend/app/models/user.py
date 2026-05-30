"""Modelo User para autenticacion."""
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from . import db


class User(db.Model):
    __tablename__ = 'users'

    ROL_ADMIN    = 'admin'
    ROL_VENDEDOR = 'vendedor'

    id         = db.Column(db.Integer, primary_key=True)
    username   = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    rol        = db.Column(db.String(20), default=ROL_VENDEDOR, nullable=False)
    activo     = db.Column(db.Boolean, default=True, nullable=False)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'rol': self.rol,
            'activo': self.activo,
        }

    def __repr__(self):
        return f'<User {self.username} ({self.rol})>'
