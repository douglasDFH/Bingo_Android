"""Modelo PDFProcesado: representa un PDF subido y procesado."""
from datetime import datetime
from . import db


class PDFProcesado(db.Model):
    __tablename__ = 'pdfs_procesados'

    id = db.Column(db.Integer, primary_key=True)
    nombre_archivo = db.Column(db.String(255), nullable=False)
    ruta_archivo = db.Column(db.String(500), nullable=False)
    fecha_procesado = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    total_paginas = db.Column(db.Integer, default=0)
    paginas_ok = db.Column(db.Integer, default=0)
    paginas_error = db.Column(db.Integer, default=0)
    carpeta_imagenes = db.Column(db.String(500))
    dpi = db.Column(db.Integer, default=100)
    estado = db.Column(db.String(20), default='pendiente')  # pendiente, procesando, completado, error
    mensaje_error = db.Column(db.Text)

    cartones = db.relationship(
        'Carton',
        backref='pdf',
        lazy='dynamic',
        cascade='all, delete-orphan',
    )

    def to_dict(self):
        return {
            'id': self.id,
            'nombre_archivo': self.nombre_archivo,
            'fecha_procesado': self.fecha_procesado.isoformat() if self.fecha_procesado else None,
            'total_paginas': self.total_paginas,
            'paginas_ok': self.paginas_ok,
            'paginas_error': self.paginas_error,
            'estado': self.estado,
            'dpi': self.dpi,
        }

    def __repr__(self):
        return f'<PDFProcesado {self.id} {self.nombre_archivo}>'
