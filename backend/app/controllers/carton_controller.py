"""Controlador de cartones: listar, ver detalle, cambiar estado."""
import os
from decimal import Decimal, InvalidOperation
from flask import (
    Blueprint, render_template, request, redirect, url_for, flash,
    send_file, abort, jsonify,
)
from sqlalchemy import or_
from ..models import db
from ..models.carton import Carton

carton_bp = Blueprint('carton', __name__)

PAGE_SIZE = 60


@carton_bp.route('/')
def listar():
    estado = request.args.get('estado', '').strip()
    busqueda = request.args.get('q', '').strip()
    page = max(int(request.args.get('page', 1)), 1)

    query = Carton.query
    if estado:
        query = query.filter(Carton.estado == estado)
    if busqueda:
        like = f'%{busqueda}%'
        query = query.filter(or_(
            Carton.numero.ilike(like),
            Carton.comprador.ilike(like),
            Carton.telefono_comprador.ilike(like),
        ))
    query = query.order_by(Carton.numero.asc())

    total = query.count()
    cartones = query.offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE).all()
    total_paginas = (total + PAGE_SIZE - 1) // PAGE_SIZE

    return render_template(
        'cartones/listar.html',
        cartones=cartones,
        estado=estado,
        busqueda=busqueda,
        page=page,
        total_paginas=total_paginas,
        total=total,
    )


@carton_bp.route('/<int:carton_id>')
def detalle(carton_id):
    carton = Carton.query.get_or_404(carton_id)
    return render_template('cartones/detalle.html', carton=carton)


@carton_bp.route('/<int:carton_id>/imagen')
def imagen(carton_id):
    """Sirve la imagen del cartón desde disco."""
    carton = Carton.query.get_or_404(carton_id)
    if not carton.ruta_imagen or not os.path.isfile(carton.ruta_imagen):
        abort(404)
    return send_file(carton.ruta_imagen)


@carton_bp.route('/<int:carton_id>/vender', methods=['POST'])
def vender(carton_id):
    carton = Carton.query.get_or_404(carton_id)
    comprador = request.form.get('comprador', '').strip()
    telefono = request.form.get('telefono', '').strip()
    precio_raw = request.form.get('precio', '').strip()
    notas = request.form.get('notas', '').strip()

    precio = None
    if precio_raw:
        try:
            precio = Decimal(precio_raw)
        except InvalidOperation:
            flash('Precio inválido', 'error')
            return redirect(url_for('carton.detalle', carton_id=carton.id))

    carton.marcar_vendido(comprador=comprador, telefono=telefono, precio=precio, notas=notas)
    db.session.commit()
    flash(f'Cartón {carton.numero} marcado como vendido.', 'success')
    return redirect(url_for('carton.detalle', carton_id=carton.id))


@carton_bp.route('/<int:carton_id>/reservar', methods=['POST'])
def reservar(carton_id):
    carton = Carton.query.get_or_404(carton_id)
    carton.estado = Carton.ESTADO_RESERVADO
    carton.comprador = request.form.get('comprador', '').strip() or carton.comprador
    carton.telefono_comprador = request.form.get('telefono', '').strip() or carton.telefono_comprador
    db.session.commit()
    flash(f'Cartón {carton.numero} reservado.', 'success')
    return redirect(url_for('carton.detalle', carton_id=carton.id))


@carton_bp.route('/<int:carton_id>/liberar', methods=['POST'])
def liberar(carton_id):
    carton = Carton.query.get_or_404(carton_id)
    carton.marcar_disponible()
    db.session.commit()
    flash(f'Cartón {carton.numero} marcado como disponible.', 'success')
    return redirect(url_for('carton.detalle', carton_id=carton.id))


@carton_bp.route('/api/buscar')
def api_buscar():
    """Endpoint JSON simple para búsqueda rápida."""
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify([])
    like = f'%{q}%'
    cartones = Carton.query.filter(or_(
        Carton.numero.ilike(like),
        Carton.comprador.ilike(like),
    )).limit(20).all()
    return jsonify([c.to_dict() for c in cartones])
