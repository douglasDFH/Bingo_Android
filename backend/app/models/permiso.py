from . import db

PERMISOS_DISPONIBLES = {
    'subir_pdf': 'Subir PDFs',
    'vender':    'Vender cartones',
    'reservar':  'Reservar cartones',
    'liberar':   'Liberar cartones reservados',
}

# Por defecto los vendedores NO pueden subir PDFs; sí pueden vender/reservar/liberar
DEFAULTS_VENDEDOR = {
    'subir_pdf': False,
    'vender':    True,
    'reservar':  True,
    'liberar':   True,
}


class PermisoRol(db.Model):
    __tablename__ = 'permisos_rol'

    id         = db.Column(db.Integer, primary_key=True)
    rol        = db.Column(db.String(20), nullable=False)
    permiso    = db.Column(db.String(50), nullable=False)
    habilitado = db.Column(db.Boolean, default=True, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('rol', 'permiso', name='uq_permiso_rol'),
    )

    @classmethod
    def get_for_rol(cls, rol):
        """Devuelve dict {permiso: bool} para el rol dado."""
        if rol == 'admin':
            return {p: True for p in PERMISOS_DISPONIBLES}
        rows = cls.query.filter_by(rol=rol).all()
        result = dict(DEFAULTS_VENDEDOR)
        for row in rows:
            if row.permiso in result:
                result[row.permiso] = row.habilitado
        return result

    @classmethod
    def seed_defaults(cls):
        """Inserta los permisos por defecto si no existen."""
        for permiso, habilitado in DEFAULTS_VENDEDOR.items():
            if not cls.query.filter_by(rol='vendedor', permiso=permiso).first():
                db.session.add(cls(rol='vendedor', permiso=permiso, habilitado=habilitado))
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
