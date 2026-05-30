"""Controlador principal: dashboard, página de inicio."""
from flask import Blueprint, render_template
from sqlalchemy import func
from ..models import db
from ..models.pdf_procesado import PDFProcesado
from ..models.carton import Carton

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    total_pdfs = PDFProcesado.query.count()
    total_cartones = Carton.query.count()
    disponibles = Carton.query.filter_by(estado=Carton.ESTADO_DISPONIBLE).count()
    vendidos = Carton.query.filter_by(estado=Carton.ESTADO_VENDIDO).count()
    reservados = Carton.query.filter_by(estado=Carton.ESTADO_RESERVADO).count()

    ingresos = db.session.query(func.sum(Carton.precio)).filter(
        Carton.estado == Carton.ESTADO_VENDIDO
    ).scalar() or 0

    ultimos_pdfs = PDFProcesado.query.order_by(
        PDFProcesado.fecha_procesado.desc()
    ).limit(5).all()

    return render_template(
        'index.html',
        total_pdfs=total_pdfs,
        total_cartones=total_cartones,
        disponibles=disponibles,
        vendidos=vendidos,
        reservados=reservados,
        ingresos=float(ingresos),
        ultimos_pdfs=ultimos_pdfs,
    )
