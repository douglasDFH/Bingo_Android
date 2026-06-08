"""Servicio de procesamiento de PDF.
Extrae el número de cada página del PDF y genera una imagen del cartón
usando el template oficial con el número superpuesto en el círculo vacío.
"""
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional

import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont

# Ruta al template del cartón (imagen "carton .jpeg")
TEMPLATE_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'static', 'carton_template.jpeg'
)

# Posición relativa del círculo vacío en el template
# Círculo superior-derecho de la imagen "carton .jpeg"
CIRCULO_CX = 0.790   # centro X (79% del ancho)
CIRCULO_CY = 0.330   # centro Y (33% del alto)
CIRCULO_R  = 0.140   # radio como fracción del ancho

# Fuentes candidatas en el servidor Linux/Docker
_FONT_CANDIDATOS = [
    '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    '/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf',
    '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
    '/usr/share/fonts/truetype/freefont/FreeSansBold.ttf',
    '/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf',
]


def _encontrar_fuente() -> Optional[str]:
    for p in _FONT_CANDIDATOS:
        if os.path.isfile(p):
            return p
    return None


FONT_PATH = _encontrar_fuente()


class PDFProcessorError(Exception):
    pass


class PDFProcessor:
    REGEX_NUMERO       = re.compile(r'^\s*(\d{3,8})\s*$')
    REGEX_NUMERO_INLINE = re.compile(r'\b(\d{3,8})\b')

    def __init__(self, dpi: int = 72, formato: str = 'jpeg'):
        self.dpi     = dpi
        self.formato = formato.lower()
        if self.formato not in ('jpeg', 'png'):
            raise ValueError("formato debe ser 'jpeg' o 'png'")
        if not os.path.isfile(TEMPLATE_PATH):
            raise PDFProcessorError(f'Template no encontrado: {TEMPLATE_PATH}')
        print(f'[BINGO] PDFProcessor: template={TEMPLATE_PATH} fuente={FONT_PATH}', flush=True)

    # ── utilidades ────────────────────────────────────────────────────────────

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

    def generar_imagen_carton(self, numero: str, ruta_destino: str) -> None:
        """
        Genera la imagen del cartón usando el template y escribe el número
        centrado en el círculo vacío (zona superior derecha).
        Thread-safe: abre el template de nuevo en cada llamada.
        """
        img  = Image.open(TEMPLATE_PATH).convert('RGB')
        draw = ImageDraw.Draw(img)
        W, H = img.size

        cx = int(W * CIRCULO_CX)
        cy = int(H * CIRCULO_CY)
        r  = int(W * CIRCULO_R)

        # Encontrar el tamaño de fuente más grande que entre en el círculo
        font      = None
        font_size = int(r * 1.4)   # empieza grande y reduce

        if FONT_PATH:
            while font_size >= 12:
                try:
                    f    = ImageFont.truetype(FONT_PATH, font_size)
                    bbox = draw.textbbox((0, 0), numero, font=f)
                    tw   = bbox[2] - bbox[0]
                    th   = bbox[3] - bbox[1]
                    # cabe si ancho y alto entran en el 85% del diámetro
                    if tw <= r * 1.70 and th <= r * 1.70:
                        font = f
                        break
                except Exception:
                    pass
                font_size -= 4

        if font is None:
            # fallback: fuente default PIL (pequeña pero siempre disponible)
            font = ImageFont.load_default()

        # Medir texto final y centrar en el círculo
        bbox = draw.textbbox((0, 0), numero, font=font)
        tw   = bbox[2] - bbox[0]
        th   = bbox[3] - bbox[1]
        x    = cx - tw // 2
        y    = cy - th // 2

        # Sombra oscura para legibilidad
        sombra = max(2, font_size // 22)
        draw.text((x + sombra, y + sombra), numero, fill='#1A0A00', font=font)
        # Texto dorado principal
        draw.text((x, y), numero, fill='#FFD700', font=font)

        os.makedirs(os.path.dirname(ruta_destino), exist_ok=True)
        img.save(ruta_destino, 'JPEG', quality=88)

    # ── procesamiento de página ───────────────────────────────────────────────

    def _procesar_pagina(self, pdf_path: str, indice: int,
                         carpeta_salida: str, ext: str) -> dict:
        """Extrae número de la página y genera imagen con el template."""
        try:
            doc = fitz.open(pdf_path)
            try:
                texto = doc.load_page(indice).get_text()
            finally:
                doc.close()

            numero = self._extraer_numero_de_texto(texto)
            if not numero:
                numero = f'sin_numero_pagina_{indice + 1}'

            ruta_destino = os.path.join(carpeta_salida, f'{numero}.{ext}')
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
                'ok':    {'indice': indice, 'numero': numero,
                          'pagina': indice + 1, 'ruta': ruta_destino},
                'error': None,
            }
        except Exception as ex:
            return {
                'ok':    None,
                'error': {'indice': indice, 'numero': None, 'razon': str(ex)},
            }

    # ── procesamiento completo del PDF ────────────────────────────────────────

    def procesar(self, pdf_path: str, carpeta_salida: str,
                 carton_cb:   Optional[Callable] = None,
                 error_cb:    Optional[Callable] = None,
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
