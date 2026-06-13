"""Modelo Grupo: agrupa usuarios vendedores de bingo."""
from datetime import datetime
from . import db


class Grupo(db.Model):
    __tablename__ = 'grupos'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(200), nullable=False, unique=True)
    activo = db.Column(db.Boolean, default=True, nullable=False)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    usuarios = db.relationship('User', backref='grupo', lazy='dynamic',
                               foreign_keys='User.grupo_id')

    def to_dict(self):
        total = self.usuarios.filter_by(activo=True).count()
        return {
            'id': self.id,
            'nombre': self.nombre,
            'activo': self.activo,
            'total_usuarios': total,
            'fecha_creacion': self.fecha_creacion.isoformat() if self.fecha_creacion else None,
        }

    def __repr__(self):
        return f'<Grupo {self.id} {self.nombre}>'
