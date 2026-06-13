"""Modelo Carton: cada cartón de bingo individual."""
from datetime import datetime
from . import db


class Carton(db.Model):
    __tablename__ = 'cartones'

    ESTADO_DISPONIBLE = 'disponible'
    ESTADO_VENDIDO = 'vendido'
    ESTADO_RESERVADO = 'reservado'

    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(20), unique=True, nullable=False, index=True)
    pdf_id = db.Column(db.Integer, db.ForeignKey('pdfs_procesados.id'), nullable=False)
    pagina_origen = db.Column(db.Integer, nullable=False)
    ruta_imagen = db.Column(db.String(500), nullable=False)
    vendedor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    grupo_id    = db.Column(db.Integer, db.ForeignKey('grupos.id'), nullable=True, index=True)

    # Estado
    estado = db.Column(db.String(20), default=ESTADO_DISPONIBLE, nullable=False, index=True)
    comprador = db.Column(db.String(200))
    telefono_comprador = db.Column(db.String(50))
    fecha_venta = db.Column(db.DateTime)
    precio = db.Column(db.Numeric(10, 2))
    notas = db.Column(db.Text)

    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_actualizacion = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def marcar_vendido(self, comprador=None, telefono=None, precio=None, notas=None):
        self.estado = self.ESTADO_VENDIDO
        self.fecha_venta = datetime.utcnow()
        if comprador:
            self.comprador = comprador
        if telefono:
            self.telefono_comprador = telefono
        if precio is not None:
            self.precio = precio
        if notas:
            self.notas = notas

    def marcar_disponible(self):
        self.estado = self.ESTADO_DISPONIBLE
        self.fecha_venta = None
        self.comprador = None
        self.telefono_comprador = None
        self.precio = None

    def to_dict(self):
        return {
            'id': self.id,
            'numero': self.numero,
            'estado': self.estado,
            'comprador': self.comprador,
            'telefono_comprador': self.telefono_comprador,
            'fecha_venta': self.fecha_venta.isoformat() if self.fecha_venta else None,
            'precio': float(self.precio) if self.precio is not None else None,
            'notas': self.notas,
            'pagina_origen': self.pagina_origen,
            'ruta_imagen': self.ruta_imagen,
            'vendedor_id': self.vendedor_id,
            'grupo_id': self.grupo_id,
        }

    def __repr__(self):
        return f'<Carton {self.numero} ({self.estado})>'
