"""API JSON para la app móvil."""
import os
import uuid
import shutil
import threading
from datetime import datetime
from decimal import Decimal, InvalidOperation
from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from sqlalchemy import func, or_
from werkzeug.utils import secure_filename
from ..models import db
from ..models.pdf_procesado import PDFProcesado
from ..models.carton import Carton
from ..models.user import User
from ..services.pdf_processor import PDFProcessor, PDFProcessorError

api_bp = Blueprint('api', __name__)


def _usuario_actual():
    """Retorna (user_id: int, rol: str) del JWT actual."""
    return int(get_jwt_identity()), get_jwt().get('rol', '')


@api_bp.before_request
@jwt_required()
def require_auth():
    pass


@api_bp.route('/usuarios')
def listar_usuarios():
    """Lista de usuarios para admin (para filtros y asignación)."""
    _, rol = _usuario_actual()
    if rol != User.ROL_ADMIN:
        return jsonify({'error': 'Se requiere rol admin'}), 403
    usuarios = User.query.filter_by(activo=True).order_by(User.username).all()
    return jsonify([u.to_dict() for u in usuarios])


@api_bp.route('/dashboard')
def dashboard():
    user_id, rol = _usuario_actual()

    base = Carton.query if rol == User.ROL_ADMIN else Carton.query.filter_by(vendedor_id=user_id)
    pdfs_base = PDFProcesado.query if rol == User.ROL_ADMIN else PDFProcesado.query.filter_by(subido_por=user_id)

    total_cartones = base.count()
    disponibles = base.filter_by(estado=Carton.ESTADO_DISPONIBLE).count()
    vendidos = base.filter_by(estado=Carton.ESTADO_VENDIDO).count()
    reservados = base.filter_by(estado=Carton.ESTADO_RESERVADO).count()
    ingresos = db.session.query(func.sum(Carton.precio)).filter(
        Carton.estado == Carton.ESTADO_VENDIDO,
        *([Carton.vendedor_id == user_id] if rol != User.ROL_ADMIN else [])
    ).scalar() or 0

    total_pdfs = pdfs_base.count()
    ultimos_pdfs = pdfs_base.order_by(PDFProcesado.fecha_procesado.desc()).limit(5).all()

    return jsonify({
        'total_pdfs': total_pdfs,
        'total_cartones': total_cartones,
        'disponibles': disponibles,
        'vendidos': vendidos,
        'reservados': reservados,
        'ingresos': float(ingresos),
        'ultimos_pdfs': [p.to_dict() for p in ultimos_pdfs],
        'es_admin': rol == User.ROL_ADMIN,
    })


@api_bp.route('/cartones')
def cartones():
    user_id, rol = _usuario_actual()
    estado = request.args.get('estado', '').strip()
    q = request.args.get('q', '').strip()
    usuario_id = request.args.get('usuario_id', type=int)
    page = max(int(request.args.get('page', 1)), 1)
    per_page = 30

    query = Carton.query
    if rol != User.ROL_ADMIN:
        query = query.filter(Carton.vendedor_id == user_id)
    elif usuario_id:
        query = query.filter(Carton.vendedor_id == usuario_id)

    if estado:
        query = query.filter(Carton.estado == estado)
    if q:
        like = f'%{q}%'
        query = query.filter(or_(
            Carton.numero.ilike(like),
            Carton.comprador.ilike(like),
            Carton.telefono_comprador.ilike(like),
        ))
    query = query.order_by(Carton.numero.asc())

    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    total_paginas = (total + per_page - 1) // per_page

    return jsonify({
        'cartones': [c.to_dict() for c in items],
        'total': total,
        'page': page,
        'total_paginas': total_paginas,
    })


@api_bp.route('/cartones/<int:carton_id>')
def carton_detalle(carton_id):
    carton = Carton.query.get_or_404(carton_id)
    return jsonify(carton.to_dict())


@api_bp.route('/cartones/<int:carton_id>/vender', methods=['POST'])
def vender(carton_id):
    carton = Carton.query.get_or_404(carton_id)
    data = request.get_json() or {}
    precio = None
    if data.get('precio'):
        try:
            precio = Decimal(str(data['precio']))
        except InvalidOperation:
            return jsonify({'error': 'Precio inválido'}), 400

    carton.marcar_vendido(
        comprador=data.get('comprador', ''),
        telefono=data.get('telefono', ''),
        precio=precio,
        notas=data.get('notas', ''),
    )
    db.session.commit()
    return jsonify(carton.to_dict())


@api_bp.route('/cartones/<int:carton_id>/reservar', methods=['POST'])
def reservar(carton_id):
    carton = Carton.query.get_or_404(carton_id)
    data = request.get_json() or {}
    carton.estado = Carton.ESTADO_RESERVADO
    if data.get('comprador'):
        carton.comprador = data['comprador']
    if data.get('telefono'):
        carton.telefono_comprador = data['telefono']
    db.session.commit()
    return jsonify(carton.to_dict())


@api_bp.route('/cartones/<int:carton_id>/liberar', methods=['POST'])
def liberar(carton_id):
    carton = Carton.query.get_or_404(carton_id)
    carton.marcar_disponible()
    db.session.commit()
    return jsonify(carton.to_dict())


@api_bp.route('/subir-pdf', methods=['POST'])
def subir_pdf():
    if 'pdf' not in request.files:
        return jsonify({'error': 'No se envió ningún archivo'}), 400

    archivo = request.files['pdf']
    if archivo.filename == '' or not archivo.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'Solo se permiten archivos PDF'}), 400

    user_id, rol = _usuario_actual()
    target_user_id = request.form.get('usuario_id', type=int) or user_id

    nombre_original = secure_filename(archivo.filename)
    nombre_unico = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}_{nombre_original}"
    ruta_pdf = os.path.join(current_app.config['UPLOAD_FOLDER'], nombre_unico)
    archivo.save(ruta_pdf)

    pdf = PDFProcesado(
        nombre_archivo=nombre_original,
        ruta_archivo=ruta_pdf,
        estado='procesando',
        dpi=current_app.config['DPI_IMAGENES'],
        subido_por=user_id,
    )
    db.session.add(pdf)
    db.session.commit()

    import threading
    app = current_app._get_current_object()
    threading.Thread(target=_procesar_pdf_async, args=(app, pdf.id, target_user_id), daemon=True).start()

    return jsonify({'ok': True, 'pdf_id': pdf.id, 'nombre': nombre_original, 'estado': 'procesando'})


@api_bp.route('/pdfs/<int:pdf_id>/estado')
def estado_pdf(pdf_id):
    pdf = PDFProcesado.query.get_or_404(pdf_id)
    data = pdf.to_dict()
    data['cartones_creados'] = pdf.paginas_ok
    data['errores'] = pdf.paginas_error
    return jsonify(data)


def _procesar_pdf_async(app, pdf_id, vendedor_id=None):
    with app.app_context():
        pdf = PDFProcesado.query.get(pdf_id)
        if not pdf:
            return
        try:
            carpeta_imgs = os.path.join(app.config['IMAGENES_FOLDER'], f'pdf_{pdf.id}')
            processor = PDFProcessor(
                dpi=app.config['DPI_IMAGENES'],
                formato=app.config['FORMATO_IMAGEN'],
            )
            resultado = processor.procesar(pdf.ruta_archivo, carpeta_imgs)

            pdf.carpeta_imagenes = carpeta_imgs
            pdf.total_paginas = resultado['total']
            pdf.paginas_ok = len(resultado['ok'])
            pdf.paginas_error = len(resultado['error'])
            pdf.estado = 'completado' if not resultado['error'] else 'completado_con_errores'

            for item in resultado['ok']:
                if Carton.query.filter_by(numero=item['numero']).first():
                    continue
                db.session.add(Carton(
                    numero=item['numero'],
                    pdf_id=pdf.id,
                    pagina_origen=item.get('pagina', item['indice'] + 1),
                    ruta_imagen=item['ruta'],
                    estado=Carton.ESTADO_DISPONIBLE,
                    vendedor_id=vendedor_id,
                ))
            db.session.commit()
        except Exception as e:
            pdf.estado = 'error'
            pdf.mensaje_error = str(e)[:1000]
            db.session.commit()


# ── Chunked upload ────────────────────────────────────────────────────────────

@api_bp.route('/upload-chunk', methods=['POST'])
def upload_chunk():
    upload_id    = request.form.get('upload_id')
    chunk_index  = request.form.get('chunk_index', type=int)
    total_chunks = request.form.get('total_chunks', type=int)
    nombre       = request.form.get('nombre', 'archivo.pdf')

    if upload_id is None or chunk_index is None or total_chunks is None:
        return jsonify({'error': 'Parametros incompletos'}), 400
    if 'chunk' not in request.files:
        return jsonify({'error': 'Sin datos'}), 400

    chunks_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'chunks', upload_id)
    os.makedirs(chunks_dir, exist_ok=True)

    request.files['chunk'].save(os.path.join(chunks_dir, f'chunk_{chunk_index:05d}'))

    meta_path = os.path.join(chunks_dir, 'meta.txt')
    if not os.path.exists(meta_path):
        with open(meta_path, 'w') as f:
            f.write(f"{nombre}\n{total_chunks}")

    return jsonify({'ok': True, 'chunk': chunk_index})


@api_bp.route('/upload-finalize', methods=['POST'])
def upload_finalize():
    data      = request.get_json() or {}
    upload_id = data.get('upload_id')

    if not upload_id:
        return jsonify({'error': 'upload_id requerido'}), 400

    chunks_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'chunks', upload_id)
    if not os.path.isdir(chunks_dir):
        return jsonify({'error': 'Upload no encontrado'}), 404

    user_id, _ = _usuario_actual()
    target_user_id = data.get('usuario_id') or user_id

    nombre_original = 'archivo.pdf'
    meta_path = os.path.join(chunks_dir, 'meta.txt')
    if os.path.exists(meta_path):
        with open(meta_path) as f:
            nombre_original = f.readline().strip()

    chunks = sorted(
        [f for f in os.listdir(chunks_dir) if f.startswith('chunk_')],
        key=lambda x: int(x.split('_')[1])
    )
    if not chunks:
        return jsonify({'error': 'Sin chunks'}), 400

    nombre_unico = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}_{secure_filename(nombre_original)}"
    ruta_pdf = os.path.join(current_app.config['UPLOAD_FOLDER'], nombre_unico)

    with open(ruta_pdf, 'wb') as out:
        for chunk_name in chunks:
            with open(os.path.join(chunks_dir, chunk_name), 'rb') as f:
                out.write(f.read())

    shutil.rmtree(chunks_dir, ignore_errors=True)

    pdf = PDFProcesado(
        nombre_archivo=nombre_original,
        ruta_archivo=ruta_pdf,
        estado='procesando',
        dpi=current_app.config['DPI_IMAGENES'],
        subido_por=user_id,
    )
    db.session.add(pdf)
    db.session.commit()

    app = current_app._get_current_object()
    threading.Thread(target=_procesar_pdf_async, args=(app, pdf.id, target_user_id), daemon=True).start()

    return jsonify({'ok': True, 'pdf_id': pdf.id, 'nombre': nombre_original, 'estado': 'procesando'})
