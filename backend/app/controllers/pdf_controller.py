"""Controlador de PDFs: subir, listar, procesar."""
import os
import uuid
from datetime import datetime
from flask import (
    Blueprint, render_template, request, redirect, url_for, flash,
    current_app, abort,
)
from werkzeug.utils import secure_filename
from ..models import db
from ..models.pdf_procesado import PDFProcesado
from ..models.carton import Carton
from ..services.pdf_processor import PDFProcessor, PDFProcessorError

pdf_bp = Blueprint('pdf', __name__)

ALLOWED_EXTENSIONS = {'pdf'}


def archivo_permitido(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@pdf_bp.route('/')
def listar():
    pdfs = PDFProcesado.query.order_by(PDFProcesado.fecha_procesado.desc()).all()
    return render_template('pdfs/listar.html', pdfs=pdfs)


@pdf_bp.route('/subir', methods=['GET', 'POST'])
def subir():
    if request.method == 'POST':
        if 'pdf' not in request.files:
            flash('No se envió ningún archivo', 'error')
            return redirect(request.url)

        archivo = request.files['pdf']
        if archivo.filename == '':
            flash('Selecciona un archivo PDF', 'error')
            return redirect(request.url)

        if not archivo_permitido(archivo.filename):
            flash('Solo se permiten archivos PDF', 'error')
            return redirect(request.url)

        # Guardar PDF con nombre único
        nombre_original = secure_filename(archivo.filename)
        nombre_unico = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}_{nombre_original}"
        ruta_pdf = os.path.join(current_app.config['UPLOAD_FOLDER'], nombre_unico)
        archivo.save(ruta_pdf)

        # Crear registro
        pdf = PDFProcesado(
            nombre_archivo=nombre_original,
            ruta_archivo=ruta_pdf,
            estado='procesando',
            dpi=current_app.config['DPI_IMAGENES'],
        )
        db.session.add(pdf)
        db.session.commit()

        # Procesar (síncrono por simplicidad — para PDFs muy grandes
        # se podría delegar a un job en background)
        try:
            carpeta_imgs = os.path.join(
                current_app.config['IMAGENES_FOLDER'],
                f'pdf_{pdf.id}',
            )
            processor = PDFProcessor(
                dpi=current_app.config['DPI_IMAGENES'],
                formato=current_app.config['FORMATO_IMAGEN'],
            )
            resultado = processor.procesar(ruta_pdf, carpeta_imgs)

            pdf.carpeta_imagenes = carpeta_imgs
            pdf.total_paginas = resultado['total']
            pdf.paginas_ok = len(resultado['ok'])
            pdf.paginas_error = len(resultado['error'])
            pdf.estado = 'completado' if not resultado['error'] else 'completado_con_errores'

            # Crear cartones
            for item in resultado['ok']:
                # evitar duplicados por número
                existente = Carton.query.filter_by(numero=item['numero']).first()
                if existente:
                    continue
                carton = Carton(
                    numero=item['numero'],
                    pdf_id=pdf.id,
                    pagina_origen=item.get('pagina', item['indice'] + 1),
                    ruta_imagen=item['ruta'],
                    estado=Carton.ESTADO_DISPONIBLE,
                )
                db.session.add(carton)

            db.session.commit()
            flash(
                f'PDF procesado: {pdf.paginas_ok} cartones creados '
                f'({pdf.paginas_error} errores).',
                'success',
            )
        except (PDFProcessorError, Exception) as e:
            pdf.estado = 'error'
            pdf.mensaje_error = str(e)[:1000]
            db.session.commit()
            flash(f'Error procesando el PDF: {e}', 'error')

        return redirect(url_for('pdf.detalle', pdf_id=pdf.id))

    return render_template('pdfs/subir.html')


@pdf_bp.route('/<int:pdf_id>')
def detalle(pdf_id):
    pdf = PDFProcesado.query.get_or_404(pdf_id)
    cartones = pdf.cartones.limit(50).all()
    total = pdf.cartones.count()
    return render_template(
        'pdfs/detalle.html', pdf=pdf, cartones=cartones, total_cartones=total
    )


@pdf_bp.route('/<int:pdf_id>/eliminar', methods=['POST'])
def eliminar(pdf_id):
    pdf = PDFProcesado.query.get_or_404(pdf_id)
    db.session.delete(pdf)
    db.session.commit()
    flash('PDF y sus cartones eliminados del registro.', 'success')
    return redirect(url_for('pdf.listar'))
