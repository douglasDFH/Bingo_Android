"""Servicio de procesamiento de PDF.
Extrae el número de cada página y genera una imagen del cartón
usando el template oficial con el número superpuesto en el círculo.
"""
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional

import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont

# Ruta al template del cartón
TEMPLATE_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'static', 'carton_template.jpeg'
)

# Posición relativa del círculo vacío en el template
# (ajustada a la imagen "carton .jpeg")
CIRCULO_CX = 0.790   # centro X como fracción del ancho
CIRCULO_CY = 0.340   # centro Y como fracción del alto
CIRCULO_R  = 0.145   # radio como fracción del ancho


class PDFProcessorError(Exception):
    pass


class PDFProcessor:
    REGEX_NUMERO      = re.compile(r'^\s*(\d{3,8})\s*$')
    REGEX_NUMERO_INLINE = re.compile(r'\b(\d{3,8})\b')

    def __init__(self, dpi: int = 72, formato: str = 'jpeg'):
        self.dpi     = dpi
        self.formato = formato.lower()
        if self.formato not in ('jpeg', 'png'):
            raise ValueError("formato debe ser 'jpeg' o 'png'")

        # Cargar template una sola vez
        if not os.path.isfile(TEMPLATE_PATH):
            raise PDFProcessorError(
                f'Template del cartón no encontrado: {TEMPLATE_PATH}'
            )
        self._template = Image.open(TEMPLATE_PATH).convert('RGB')

        # Buscar fuente
        self._font_path = self._encontrar_fuente()

    # ── utilidades ────────────────────────────────────────────────────────────

    @staticmethod
    def _encontrar_fuente():
        candidatos = [
            '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
            '/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
            '/usr/share/fonts/truetype/freefont/FreeSansBold.ttf',
        ]
        for p in candidatos:
            if os.path.isfile(p):
                return p
        return None  # usará fuente default de PIL

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
        """Convierte el número extraído del PDF a exactamente 5 dígitos.
        Ejemplo: '100001' → '00001', '42' → '00042'.
        """
        try:
            n = abs(int(numero_str)) % 100000
            return str(n).zfill(5)
        except (ValueError, TypeError):
            return numero_str

    def generar_imagen_carton(self, numero: str, ruta_destino: str) -> None:
        """Crea la imagen del cartón usando el template y escribe el número
        centrado en el círculo vacío de la zona superior derecha."""
        img  = self._template.copy()
        draw = ImageDraw.Draw(img)
        W, H = img.size

        # Centro y radio del círculo en píxeles
        cx = int(W * CIRCULO_CX)
        cy = int(H * CIRCULO_CY)
        r  = int(W * CIRCULO_R)

        # Tamaño de fuente: que el texto ocupe ~75% del diámetro
        font_size = int(r * 1.0)   # 1 radio = buen tamaño para 5 chars
        font = None
        if self._font_path:
            try:
                font = ImageFont.truetype(self._font_path, font_size)
            except Exception:
                font = None

        if font is None:
            # Fuente default de PIL (muy pequeña, pero funcional)
            font = ImageFont.load_default()

        # Medir texto y centrar
        bbox = draw.textbbox((0, 0), numero, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        x  = cx - tw // 2
        y  = cy - th // 2

        # Sombra oscura para legibilidad
        shadow_offset = max(2, font_size // 20)
        draw.text((x + shadow_offset, y + shadow_offset),
                  numero, fill='#2D0A00', font=font)
        # Texto dorado principal
        draw.text((x, y), numero, fill='#FFD700', font=font)

        os.makedirs(os.path.dirname(ruta_destino), exist_ok=True)
        img.save(ruta_destino, 'JPEG', quality=88)

    # ── procesamiento ─────────────────────────────────────────────────────────

    def _procesar_pagina(self, pdf_path: str, indice: int,
                         carpeta_salida: str, ext: str) -> dict:
        """Extrae el número de la página y genera la imagen del cartón."""
        try:
            doc = fitz.open(pdf_path)
            try:
                texto  = doc.load_page(indice).get_text()
            finally:
                doc.close()

            numero = self._extraer_numero_de_texto(texto)
            if numero:
                numero = self.formatear_numero(numero)
            else:
                numero = f'sin_numero_{str(indice + 1).zfill(5)}'

            ruta_destino = os.path.join(carpeta_salida, f'{numero}.{ext}')
            # Evitar sobreescribir si ya existe un número igual
            if os.path.exists(ruta_destino):
                contador = 2
                while True:
                    alt = os.path.join(carpeta_salida, f'{numero}_{contador}.{ext}')
                    if not os.path.exists(alt):
                        ruta_destino = alt
                        break
                    contador += 1

            self.generar_imagen_carton(numero, ruta_destino)

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
                 error_cb:  Optional[Callable] = None,
                 progreso_cb: Optional[Callable] = None) -> dict:
        if not os.path.isfile(pdf_path):
            raise PDFProcessorError(f'PDF no encontrado: {pdf_path}')
        os.makedirs(carpeta_salida, exist_ok=True)
        ext = 'jpg' if self.formato == 'jpeg' else 'png'

        try:
            doc   = fitz.open(pdf_path)
            total = doc.page_count
            doc.close()
        except Exception as e:
            raise PDFProcessorError(f'No se pudo abrir el PDF: {e}')

        ok, error = [], []

        with ThreadPoolExecutor(max_workers=3) as executor:
            futuros = {
                executor.submit(
                    self._procesar_pagina, pdf_path, i, carpeta_salida, ext
                ): i
                for i in range(total)
            }
            for futuro in as_completed(futuros):
                resultado = futuro.result()
                if resultado['ok']:
                    ok.append(resultado['ok'])
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
