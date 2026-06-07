"""Servicio de procesamiento de PDF con procesamiento paralelo de páginas."""
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional

import fitz  # PyMuPDF


class PDFProcessorError(Exception):
    pass


class PDFProcessor:
    REGEX_NUMERO = re.compile(r'^\s*(\d{3,8})\s*$')
    REGEX_NUMERO_INLINE = re.compile(r'\b(\d{3,8})\b')

    def __init__(self, dpi: int = 72, formato: str = 'jpeg'):
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

    @staticmethod
    def formatear_numero(numero_str: str) -> str:
        """Convierte cualquier número extraído del PDF a exactamente 5 dígitos.
        Ejemplo: '100001' → '00001', '42' → '00042', '99999' → '99999'
        Si supera 5 dígitos toma los últimos 5.
        """
        try:
            n = abs(int(numero_str)) % 100000
            return str(n).zfill(5)
        except (ValueError, TypeError):
            return numero_str

    def _procesar_pagina(self, pdf_path: str, indice: int,
                         carpeta_salida: str, ext: str) -> dict:
        """Procesa una sola página. Thread-safe: abre su propia instancia del PDF."""
        try:
            zoom = self.dpi / 72.0
            matriz = fitz.Matrix(zoom, zoom)
            doc = fitz.open(pdf_path)
            try:
                page = doc.load_page(indice)
                texto = page.get_text()
                numero = self._extraer_numero_de_texto(texto)
                if numero:
                    numero = self.formatear_numero(numero)
                else:
                    numero = f'sin_numero_{str(indice + 1).zfill(5)}'
                pix = page.get_pixmap(matrix=matriz, alpha=False)
            finally:
                doc.close()

            ruta_destino = os.path.join(carpeta_salida, f'{numero}.{ext}')
            if os.path.exists(ruta_destino):
                contador = 2
                while True:
                    alt = os.path.join(carpeta_salida, f'{numero}_{contador}.{ext}')
                    if not os.path.exists(alt):
                        ruta_destino = alt
                        break
                    contador += 1

            if self.formato == 'jpeg':
                pix.save(ruta_destino, jpg_quality=75)
            else:
                pix.save(ruta_destino)

            return {
                'ok': {'indice': indice, 'numero': numero,
                       'pagina': indice + 1, 'ruta': ruta_destino},
                'error': None,
            }
        except Exception as ex:
            return {
                'ok': None,
                'error': {'indice': indice, 'numero': None, 'razon': str(ex)},
            }

    def procesar(self, pdf_path: str, carpeta_salida: str,
                 carton_cb: Optional[Callable] = None,
                 error_cb: Optional[Callable] = None,
                 progreso_cb: Optional[Callable] = None) -> dict:
        """
        Procesa el PDF en paralelo (3 workers).
        carton_cb(item): llamado en el hilo principal cuando cada página OK termina.
        error_cb(item): llamado cuando una página falla.
        """
        if not os.path.isfile(pdf_path):
            raise PDFProcessorError(f'No se pudo abrir el PDF: {pdf_path}')
        os.makedirs(carpeta_salida, exist_ok=True)
        ext = 'jpg' if self.formato == 'jpeg' else 'png'

        try:
            doc = fitz.open(pdf_path)
            total = doc.page_count
            doc.close()
        except Exception as e:
            raise PDFProcessorError(f'No se pudo abrir el PDF: {e}')

        ok, error = [], []

        with ThreadPoolExecutor(max_workers=3) as executor:
            futuros = {
                executor.submit(self._procesar_pagina, pdf_path, i, carpeta_salida, ext): i
                for i in range(total)
            }
            for futuro in as_completed(futuros):
                resultado = futuro.result()
                if resultado['ok']:
                    ok.append(resultado['ok'])
                    # Callback en tiempo real para guardar cartón inmediatamente
                    if carton_cb:
                        try:
                            carton_cb(resultado['ok'])
                        except Exception:
                            pass
                else:
                    error.append(resultado['error'])
                    if error_cb:
                        try:
                            error_cb(resultado['error'])
                        except Exception:
                            pass
                if progreso_cb:
                    try:
                        progreso_cb(len(ok) + len(error), total)
                    except Exception:
                        pass

        ok.sort(key=lambda x: x['indice'])
        return {'ok': ok, 'error': error, 'total': total}
