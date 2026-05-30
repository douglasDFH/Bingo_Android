"""
Servicio de procesamiento de PDF.

Recibe la ruta de un PDF, extrae los números del pie de cada página y
genera una imagen JPG (o PNG) por cada página, nombrada con ese número.

Usa PyMuPDF (fitz) — instalable solo con pip, sin binarios externos.
"""
import os
import re
from typing import Callable, Optional

import fitz  # PyMuPDF


class PDFProcessorError(Exception):
    """Error genérico del procesador."""


class PDFProcessor:
    REGEX_NUMERO = re.compile(r'^\s*(\d{3,8})\s*$')
    REGEX_NUMERO_INLINE = re.compile(r'\b(\d{3,8})\b')

    def __init__(self, dpi: int = 100, formato: str = 'jpeg'):
        self.dpi = dpi
        self.formato = formato.lower()
        if self.formato not in ('jpeg', 'png'):
            raise ValueError("formato debe ser 'jpeg' o 'png'")

    def _extraer_numero_de_texto(self, texto: str):
        lines = [l.strip() for l in texto.split('\n') if l.strip()]
        if not lines:
            return None
        m = self.REGEX_NUMERO.match(lines[-1])
        if m:
            return m.group(1)
        for line in reversed(lines[-3:]):
            m = self.REGEX_NUMERO_INLINE.search(line)
            if m:
                return m.group(1)
        return None

    def procesar(self, pdf_path: str, carpeta_salida: str,
                 progreso_cb: Optional[Callable[[int, int], None]] = None) -> dict:
        if not os.path.isfile(pdf_path):
            raise FileNotFoundError(pdf_path)
        os.makedirs(carpeta_salida, exist_ok=True)
        ext = 'jpg' if self.formato == 'jpeg' else 'png'
        ok, error = [], []
        zoom = self.dpi / 72.0
        matriz = fitz.Matrix(zoom, zoom)
        try:
            doc = fitz.open(pdf_path)
        except Exception as e:
            raise PDFProcessorError(f'No se pudo abrir el PDF: {e}')
        total = doc.page_count
        try:
            for i in range(total):
                try:
                    page = doc.load_page(i)
                    texto = page.get_text()
                    numero = self._extraer_numero_de_texto(texto)
                    if not numero:
                        numero = f'sin_numero_pagina_{i+1}'
                    pix = page.get_pixmap(matrix=matriz, alpha=False)
                    ruta_destino = os.path.join(carpeta_salida, f'{numero}.{ext}')
                    if os.path.exists(ruta_destino):
                        contador = 2
                        while True:
                            alt = os.path.join(carpeta_salida, f'{numero}_{contador}.{ext}')
                            if not os.path.exists(alt):
                                ruta_destino = alt
                                break
                            contador += 1
                    pix.save(ruta_destino)
                    ok.append({
                        'indice': i, 'numero': numero,
                        'pagina': i + 1, 'ruta': ruta_destino,
                    })
                except Exception as ex:
                    error.append({'indice': i, 'numero': None, 'razon': str(ex)})
                if progreso_cb and (i + 1) % 50 == 0:
                    progreso_cb(i + 1, total)
        finally:
            doc.close()
        if progreso_cb:
            progreso_cb(total, total)
        return {'ok': ok, 'error': error, 'total': total}
