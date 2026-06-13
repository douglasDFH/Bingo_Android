"""API JSON para la app móvil."""
import os
import uuid
import shutil
import threading
from datetime import datetime
from decimal import Decimal, InvalidOperation
from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from sqlalchemy import func, or_, and_
from werkzeug.utils import secure_filename
from ..models import db
from ..models.pdf_procesado import PDFProcesado
from ..models.carton import Carton
from ..models.user import User
from ..models.grupo import Grupo
from ..services.pdf_processor import PDFProcessor, PDFProcessorError

api_bp = Blueprint('api', __name__)


def _usuario_actual():
    """Retorna (user_id: int, rol: str) del JWT actual."""
    return int(get_jwt_identity()), get_jwt().get('rol', '')


def _disponibles_subq(grupo_id_usuario):
    """IDs de cartones disponibles globalmente, uno por número único.
    Todos los vendedores ven disponibles de TODOS los grupos.
    Si el usuario tiene grupo, se prioriza su versión (banner correcto).
    Usa ROW_NUMBER() para seleccionar un representante por número.
    """
    from sqlalchemy import case as sa_case

    occ = db.session.query(Carton.numero).filter(
        Carton.estado.in_([Carton.ESTADO_RESERVADO, Carton.ESTADO_VENDIDO])
    ).subquery()

    # Prioridad: grupo del usuario = 0 (primero), cualquier otro grupo = 1
    priority = (
        sa_case((Carton.grupo_id == grupo_id_usuario, 0), else_=1)
        if grupo_id_usuario else Carton.id
    )

    rn = func.row_number().over(
        partition_by=Carton.numero,
        order_by=[priority, Carton.id]
    ).label('rn')

    inner = db.session.query(Carton.id, rn).filter(
        Carton.estado == Carton.ESTADO_DISPONIBLE,
        Carton.numero.notin_(occ)
    ).subquery()

    return db.session.query(inner.c.id).filter(inner.c.rn == 1)


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

    if rol == User.ROL_ADMIN:
        disponibles  = Carton.query.filter_by(estado=Carton.ESTADO_DISPONIBLE).count()
        vendidos     = Carton.query.filter_by(estado=Carton.ESTADO_VENDIDO).count()
        reservados   = Carton.query.filter_by(estado=Carton.ESTADO_RESERVADO).count()
        ingresos     = db.session.query(func.sum(Carton.precio)).filter_by(
            estado=Carton.ESTADO_VENDIDO).scalar() or 0
        total_pdfs   = PDFProcesado.query.count()
        ultimos_pdfs = PDFProcesado.query.order_by(PDFProcesado.fecha_procesado.desc()).limit(5).all()
    else:
        usuario = User.query.get(user_id)
        grupo_id = usuario.grupo_id if usuario else None

        # Disponibles: globales (no ocupados en ningún grupo), versión del grupo del usuario
        disponibles = Carton.query.filter(
            Carton.id.in_(_disponibles_subq(grupo_id))
        ).count()

        # Reservados y vendidos: solo los propios
        reservados = Carton.query.filter_by(vendedor_id=user_id, estado=Carton.ESTADO_RESERVADO).count()
        vendidos   = Carton.query.filter_by(vendedor_id=user_id, estado=Carton.ESTADO_VENDIDO).count()
        ingresos   = db.session.query(func.sum(Carton.precio)).filter_by(
            vendedor_id=user_id, estado=Carton.ESTADO_VENDIDO).scalar() or 0

        total_pdfs   = PDFProcesado.query.filter_by(subido_por=user_id).count()
        ultimos_pdfs = (PDFProcesado.query.filter_by(subido_por=user_id)
                        .order_by(PDFProcesado.fecha_procesado.desc()).limit(5).all())

    total_cartones = disponibles + reservados + vendidos

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
    grupo_id_filter = request.args.get('grupo_id', type=int)
    page = max(int(request.args.get('page', 1)), 1)
    per_page = 30

    query = Carton.query

    if rol == User.ROL_ADMIN:
        # Admin: puede filtrar por usuario o grupo
        if usuario_id:
            query = query.filter(Carton.vendedor_id == usuario_id)
        elif grupo_id_filter:
            query = query.filter(Carton.grupo_id == grupo_id_filter)
    else:
        # No-admin: visibilidad por grupo
        usuario = User.query.get(user_id)
        grupo_id_usuario = usuario.grupo_id if usuario else None

        if estado == Carton.ESTADO_DISPONIBLE:
            # Disponibles globales: todos los números no ocupados en ningún grupo,
            # mostrando la versión del grupo del usuario (banner correcto)
            query = Carton.query.filter(
                Carton.id.in_(_disponibles_subq(grupo_id_usuario))
            )
        elif estado in (Carton.ESTADO_RESERVADO, Carton.ESTADO_VENDIDO):
            # Reservados y vendidos: solo los propios del usuario
            query = query.filter(Carton.vendedor_id == user_id, Carton.estado == estado)
        else:
            # Todos: disponibles globales + propios reservados/vendidos
            avail_ids = _disponibles_subq(grupo_id_usuario)
            query = Carton.query.filter(
                or_(
                    Carton.id.in_(avail_ids),
                    and_(
                        Carton.vendedor_id == user_id,
                        Carton.estado.in_([Carton.ESTADO_RESERVADO, Carton.ESTADO_VENDIDO])
                    )
                )
            )

    if estado and rol == User.ROL_ADMIN:
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


@api_bp.route('/buscar-numero')
def buscar_numero():
    """Busca un número de cartón globalmente y devuelve quién lo tiene si está ocupado."""
    _, _ = _usuario_actual()
    numero = request.args.get('q', '').strip()
    if not numero:
        return jsonify({'error': 'Se requiere q'}), 400

    carton_occ = Carton.query.filter(
        Carton.numero == numero,
        Carton.estado.in_([Carton.ESTADO_RESERVADO, Carton.ESTADO_VENDIDO])
    ).first()

    if carton_occ:
        vendedor = User.query.get(carton_occ.vendedor_id) if carton_occ.vendedor_id else None
        grupo = Grupo.query.get(vendedor.grupo_id) if vendedor and vendedor.grupo_id else None
        return jsonify({
            'encontrado': True,
            'disponible': False,
            'estado': carton_occ.estado,
            'vendedor': vendedor.username if vendedor else 'Desconocido',
            'grupo': grupo.nombre if grupo else '',
            'comprador': carton_occ.comprador or '',
        })

    existe = Carton.query.filter_by(numero=numero).first()
    return jsonify({'encontrado': bool(existe), 'disponible': bool(existe)})


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
    banner_id = request.form.get('banner_id', type=int)

    # Resolución de grupo y usuarios
    grupo_id = request.form.get('grupo_id', type=int)
    usuarios_ids_str = request.form.get('usuarios_ids', '')
    usuarios_ids = [int(x) for x in usuarios_ids_str.split(',') if x.strip().isdigit()] if usuarios_ids_str else []
    # Si no se envió grupo y el usuario no es admin, usar su propio grupo
    if not grupo_id:
        uploader = User.query.get(user_id)
        if uploader and uploader.grupo_id:
            grupo_id = uploader.grupo_id
    # Fallback: asignar al propio usuario si no hay grupo
    target_user_id = request.form.get('usuario_id', type=int) or (user_id if not grupo_id else None)

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
    threading.Thread(
        target=_procesar_pdf_async,
        args=(app, pdf.id, target_user_id, banner_id, grupo_id, usuarios_ids or None),
        daemon=True,
    ).start()

    return jsonify({'ok': True, 'pdf_id': pdf.id, 'nombre': nombre_original, 'estado': 'procesando'})


@api_bp.route('/pdfs')
def listar_pdfs():
    user_id, rol = _usuario_actual()
    base = PDFProcesado.query if rol == User.ROL_ADMIN else PDFProcesado.query.filter_by(subido_por=user_id)
    pdfs = base.order_by(PDFProcesado.fecha_procesado.desc()).all()
    resultado = []
    for p in pdfs:
        d = p.to_dict()
        d['total_cartones'] = p.cartones.count()
        resultado.append(d)
    return jsonify(resultado)


@api_bp.route('/pdfs/<int:pdf_id>/estado')
def estado_pdf(pdf_id):
    pdf = PDFProcesado.query.get_or_404(pdf_id)
    data = pdf.to_dict()
    data['cartones_creados'] = pdf.paginas_ok
    data['errores'] = pdf.paginas_error
    return jsonify(data)


@api_bp.route('/pdfs/<int:pdf_id>', methods=['DELETE'])
def eliminar_pdf(pdf_id):
    user_id, rol = _usuario_actual()
    pdf = PDFProcesado.query.get_or_404(pdf_id)
    if rol != User.ROL_ADMIN and pdf.subido_por != user_id:
        return jsonify({'error': 'Sin permiso'}), 403
    carpeta = pdf.carpeta_imagenes
    db.session.delete(pdf)
    db.session.commit()
    if carpeta and os.path.isdir(carpeta):
        import shutil as _shutil
        _shutil.rmtree(carpeta, ignore_errors=True)
    if pdf.ruta_archivo and os.path.isfile(pdf.ruta_archivo):
        os.remove(pdf.ruta_archivo)
    return jsonify({'ok': True})


@api_bp.route('/cartones/<int:carton_id>', methods=['DELETE'])
def eliminar_carton(carton_id):
    user_id, rol = _usuario_actual()
    carton = Carton.query.get_or_404(carton_id)
    if rol != User.ROL_ADMIN and carton.vendedor_id != user_id:
        return jsonify({'error': 'Sin permiso'}), 403
    ruta_img = carton.ruta_imagen
    db.session.delete(carton)
    db.session.commit()
    if ruta_img and os.path.isfile(ruta_img):
        os.remove(ruta_img)
    return jsonify({'ok': True})


def _resolver_banner_path(banner_id):
    """Retorna la ruta del banner, None (sin banner) o _USE_DEFAULT (logo predeterminado)."""
    if banner_id is None:
        return PDFProcessor._USE_DEFAULT  # comportamiento original
    if banner_id == 0:
        return None  # sin banner: PDF original
    from ..models.banner import Banner as BannerModel
    b = BannerModel.query.get(banner_id)
    if b and os.path.isfile(b.ruta_imagen):
        return b.ruta_imagen
    print(f'[BINGO] AVISO: banner_id={banner_id} no encontrado, usando logo predeterminado', flush=True)
    return PDFProcessor._USE_DEFAULT


def _procesar_pdf_async(app, pdf_id, vendedor_id=None, banner_id=None,
                        grupo_id=None, usuarios_ids=None):
    with app.app_context():
        pdf = PDFProcesado.query.get(pdf_id)
        if not pdf:
            return
        try:
            carpeta_imgs = os.path.join(app.config['IMAGENES_FOLDER'], f'pdf_{pdf.id}')
            banner_path = _resolver_banner_path(banner_id)
            processor_kwargs = dict(
                dpi=app.config['DPI_IMAGENES'],
                formato=app.config['FORMATO_IMAGEN'],
            )
            if banner_path is not PDFProcessor._USE_DEFAULT:
                processor_kwargs['banner_path'] = banner_path
            processor = PDFProcessor(**processor_kwargs)

            pdf.carpeta_imagenes = carpeta_imgs
            db.session.commit()

            # Resolver lista de usuarios para distribución round-robin
            if grupo_id:
                if usuarios_ids:
                    asignados = [User.query.get(uid) for uid in usuarios_ids]
                    asignados = [u for u in asignados if u and u.activo]
                else:
                    asignados = (User.query.filter_by(grupo_id=grupo_id, activo=True)
                                 .order_by(User.id).all())
            else:
                asignados = [User.query.get(vendedor_id)] if vendedor_id else []
                asignados = [u for u in asignados if u]

            from threading import Lock
            _lock = Lock()
            carton_counter = [0]

            pendientes = []

            def guardar_carton(item):
                """Llamado por el procesador cada vez que termina una página."""
                if Carton.query.filter_by(numero=item['numero'], grupo_id=grupo_id).first():
                    return

                with _lock:
                    idx = carton_counter[0]
                    carton_counter[0] += 1

                if asignados:
                    assigned_user = asignados[idx % len(asignados)]
                    assigned_vendedor_id = assigned_user.id
                else:
                    assigned_vendedor_id = vendedor_id

                db.session.add(Carton(
                    numero=item['numero'],
                    pdf_id=pdf.id,
                    pagina_origen=item.get('pagina', item['indice'] + 1),
                    ruta_imagen=item['ruta'],
                    estado=Carton.ESTADO_DISPONIBLE,
                    vendedor_id=assigned_vendedor_id,
                    grupo_id=grupo_id,
                ))
                pdf.paginas_ok = (pdf.paginas_ok or 0) + 1
                pendientes.append(1)
                if len(pendientes) % 5 == 0:
                    db.session.commit()

            def on_error(item):
                pdf.paginas_error = (pdf.paginas_error or 0) + 1

            resultado = processor.procesar(
                pdf.ruta_archivo, carpeta_imgs,
                carton_cb=guardar_carton,
                error_cb=on_error,
            )

            pdf.total_paginas = resultado['total']
            pdf.paginas_ok = len(resultado['ok'])
            pdf.paginas_error = len(resultado['error'])
            pdf.estado = 'completado' if not resultado['error'] else 'completado_con_errores'
            db.session.commit()
            print(f'[BINGO] PDF {pdf_id} procesado: {pdf.paginas_ok} cartones, {pdf.paginas_error} errores', flush=True)

        except Exception as e:
            import traceback
            print(f'[BINGO] ERROR procesando PDF {pdf_id}: {e}\n{traceback.format_exc()}', flush=True)
            try:
                pdf.estado = 'error'
                pdf.mensaje_error = str(e)[:1000]
                db.session.commit()
            except Exception:
                pass


# ── Admin: regenerar imágenes con template ───────────────────────────────────

def _regenerar_imagenes_async(app):
    """
    Hilo de fondo: regenera cada imagen de cartón re-procesando la página
    original del PDF para producir el formato portrait con grilla BINGO.
    Si el PDF ya no existe, superpone el número sobre la imagen actual.
    """
    with app.app_context():
        from ..services.pdf_processor import PDFProcessor
        try:
            processor = PDFProcessor(
                dpi=app.config['DPI_IMAGENES'],
                formato=app.config['FORMATO_IMAGEN'],
            )
        except Exception as e:
            print(f'[BINGO] regenerar ERROR init: {e}', flush=True)
            return

        cartones  = Carton.query.all()
        total     = len(cartones)
        ok_count  = 0
        err_count = 0

        print(f'[BINGO] regenerar_imagenes: iniciando {total} cartones', flush=True)

        for carton in cartones:
            try:
                if not carton.ruta_imagen or not os.path.isfile(carton.ruta_imagen):
                    err_count += 1
                    print(f'[BINGO] regenerar SKIP {carton.numero}: imagen no encontrada', flush=True)
                    continue

                # Intentar regenerar desde el PDF original
                pdf_path = None
                if carton.pdf_id:
                    pdf_rec = PDFProcesado.query.get(carton.pdf_id)
                    if pdf_rec and pdf_rec.ruta_archivo and os.path.isfile(pdf_rec.ruta_archivo):
                        pdf_path = pdf_rec.ruta_archivo

                if pdf_path and carton.pagina_origen:
                    processor.regenerar_desde_pdf(
                        pdf_path,
                        carton.pagina_origen,
                        carton.ruta_imagen,
                        carton.numero or '',
                    )
                else:
                    # PDF no disponible: solo superponer número sobre imagen existente
                    processor.superponer_numero_en_archivo(carton.ruta_imagen, carton.numero or '')

                ok_count += 1
                if ok_count % 20 == 0:
                    print(f'[BINGO] regenerar progreso: {ok_count}/{total}', flush=True)
            except Exception as e:
                err_count += 1
                print(f'[BINGO] regenerar ERROR carton {carton.numero}: {e}', flush=True)

        print(f'[BINGO] regenerar_imagenes LISTO: {ok_count} OK, {err_count} errores', flush=True)


@api_bp.route('/admin/regenerar-imagenes', methods=['POST'])
def regenerar_imagenes():
    """Inicia la regeneración de imágenes en segundo plano y responde de inmediato."""
    _, rol = _usuario_actual()
    if rol != User.ROL_ADMIN:
        return jsonify({'error': 'Solo admin'}), 403

    total = Carton.query.count()
    app   = current_app._get_current_object()
    threading.Thread(target=_regenerar_imagenes_async, args=(app,), daemon=True).start()

    return jsonify({
        'ok': True,
        'mensaje': f'Regeneración iniciada en segundo plano para {total} cartones. '
                   f'En unos minutos todas las imágenes estarán actualizadas.',
        'total': total,
    })


# ── Migración de números a 5 dígitos ─────────────────────────────────────────

@api_bp.route('/admin/migrar-numeros', methods=['POST'])
def migrar_numeros():
    """Endpoint de migración (actualmente sin operación activa)."""
    _, rol = _usuario_actual()
    if rol != User.ROL_ADMIN:
        return jsonify({'error': 'Solo admin'}), 403
    return jsonify({'ok': True, 'mensaje': 'Sin cambios pendientes.'})


# ── Chunked upload ────────────────────────────────────────────────────────────

@api_bp.route('/pdf-parte', methods=['POST'])
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


@api_bp.route('/pdf-completar', methods=['POST'])
def upload_finalize():
    try:
        data      = request.get_json(force=True) or {}
    except Exception:
        data = {}
    upload_id = data.get('upload_id')

    if not upload_id:
        return jsonify({'error': 'upload_id requerido'}), 400

    chunks_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'chunks', upload_id)
    if not os.path.isdir(chunks_dir):
        return jsonify({'error': 'Upload no encontrado. Puede que el contenedor se reinicio.'}), 404

    try:
        user_id, _ = _usuario_actual()
    except Exception as e:
        return jsonify({'error': f'Auth error: {e}'}), 401

    banner_id = data.get('banner_id')
    if banner_id is not None:
        try:
            banner_id = int(banner_id)
        except (TypeError, ValueError):
            banner_id = None

    # Resolución de grupo y usuarios
    grupo_id = data.get('grupo_id') or None
    if grupo_id:
        try:
            grupo_id = int(grupo_id)
        except (TypeError, ValueError):
            grupo_id = None
    usuarios_ids = data.get('usuarios_ids') or []
    if isinstance(usuarios_ids, list):
        usuarios_ids = [int(x) for x in usuarios_ids if str(x).isdigit()]
    else:
        usuarios_ids = []

    # Si no se envió grupo, usar el grupo del usuario que sube
    if not grupo_id:
        uploader = User.query.get(user_id)
        if uploader and uploader.grupo_id:
            grupo_id = uploader.grupo_id

    target_user_id = data.get('usuario_id') or (user_id if not grupo_id else None)

    nombre_original = 'archivo.pdf'
    meta_path = os.path.join(chunks_dir, 'meta.txt')
    if os.path.exists(meta_path):
        try:
            with open(meta_path) as f:
                nombre_original = f.readline().strip()
        except Exception:
            pass

    try:
        chunks = sorted(
            [f for f in os.listdir(chunks_dir) if f.startswith('chunk_')],
            key=lambda x: int(x.split('_')[1])
        )
    except Exception as e:
        return jsonify({'error': f'Error listando chunks: {e}'}), 500

    if not chunks:
        return jsonify({'error': 'Sin chunks'}), 400

    nombre_unico = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}_{secure_filename(nombre_original)}"
    ruta_pdf = os.path.join(current_app.config['UPLOAD_FOLDER'], nombre_unico)

    try:
        with open(ruta_pdf, 'wb') as out:
            for chunk_name in chunks:
                with open(os.path.join(chunks_dir, chunk_name), 'rb') as f:
                    out.write(f.read())
    except Exception as e:
        return jsonify({'error': f'Error ensamblando PDF: {e}'}), 500

    shutil.rmtree(chunks_dir, ignore_errors=True)

    try:
        pdf = PDFProcesado(
            nombre_archivo=nombre_original,
            ruta_archivo=ruta_pdf,
            estado='procesando',
            dpi=current_app.config['DPI_IMAGENES'],
            subido_por=user_id,
        )
        db.session.add(pdf)
        db.session.commit()
    except Exception as e:
        return jsonify({'error': f'Error en base de datos: {e}'}), 500

    app = current_app._get_current_object()
    threading.Thread(
        target=_procesar_pdf_async,
        args=(app, pdf.id, target_user_id, banner_id, grupo_id, usuarios_ids or None),
        daemon=True,
    ).start()

    print(f'[BINGO] upload_finalize OK: pdf_id={pdf.id} nombre={nombre_original} '
          f'banner_id={banner_id} grupo_id={grupo_id}', flush=True)
    return jsonify({'ok': True, 'pdf_id': pdf.id, 'nombre': nombre_original, 'estado': 'procesando'})
