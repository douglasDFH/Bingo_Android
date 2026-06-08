"""Servicio de procesamiento de PDF.
Renderiza cada página del PDF como imagen y superpone el número
del cartón ("Nro # XXXXXX") en el óvalo dorado de la esquina superior derecha.
"""
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional

import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont

# Posición relativa del centro del óvalo dorado en la imagen del cartón
# (calibrado sobre "carton final.jpeg" — esquina superior derecha)
OVALO_CX   = 0.730   # centro X como fracción del ancho
OVALO_CY   = 0.155   # centro Y como fracción del alto

# Fuentes candidatas en Linux/Docker
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
        print(f'[BINGO] PDFProcessor init: dpi={dpi} fuente={FONT_PATH}', flush=True)

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

    def _superponer_numero(self, img: Image.Image, numero: str) -> Image.Image:
        """
        Superpone 'Nro #' y el número del cartón en el óvalo dorado
        de la esquina superior derecha del cartón.
        """
        draw = ImageDraw.Draw(img)
        W, H = img.size

        # Centro del óvalo dorado
        cx = int(W * OVALO_CX)
        cy = int(H * OVALO_CY)

        # ── Fuente del número (tamaño adaptativo) ──────────────────────────
        font_num  = None
        font_label = None
        max_ancho  = int(W * 0.27)   # el número no puede pasar del 27% del ancho

        if FONT_PATH:
            # Número grande
            size_num = int(W * 0.10)
            while size_num >= 10:
                try:
                    f    = ImageFont.truetype(FONT_PATH, size_num)
                    bbox = draw.textbbox((0, 0), numero, font=f)
                    if (bbox[2] - bbox[0]) <= max_ancho:
                        font_num = f
                        break
                except Exception:
                    pass
                size_num -= 2

            # Label "Nro #" (más pequeño que el número)
            size_label = max(10, size_num // 2)
            try:
                font_label = ImageFont.truetype(FONT_PATH, size_label)
            except Exception:
                font_label = None

        if font_num is None:
            font_num   = ImageFont.load_default()
        if font_label is None:
            font_label = ImageFont.load_default()

        # ── Posición del label "Nro #" ─────────────────────────────────────
        bbox_label = draw.textbbox((0, 0), "Nro #", font=font_label)
        lw = bbox_label[2] - bbox_label[0]
        lh = bbox_label[3] - bbox_label[1]
        # el label queda centrado, encima del número
        lx = cx - lw // 2
        ly = cy - lh - int(H * 0.045)

        # ── Posición del número ────────────────────────────────────────────
        bbox_num = draw.textbbox((0, 0), numero, font=font_num)
        nw = bbox_num[2] - bbox_num[0]
        nh = bbox_num[3] - bbox_num[1]
        nx = cx - nw // 2
        ny = cy - nh // 2 + int(H * 0.010)

        # ── Dibujar "Nro #" en gris oscuro ────────────────────────────────
        draw.text((lx + 1, ly + 1), "Nro #", fill='#888888', font=font_label)
        draw.text((lx,     ly    ), "Nro #", fill='#444444', font=font_label)

        # ── Dibujar número en negro con sombra ────────────────────────────
        sombra = max(1, size_num // 20) if FONT_PATH else 1
        draw.text((nx + sombra, ny + sombra), numero, fill='#333333', font=font_num)
        draw.text((nx,          ny          ), numero, fill='#111111', font=font_num)

        return img

    def superponer_numero_en_archivo(self, ruta_imagen: str, numero: str) -> None:
        """
        Carga una imagen existente y superpone el número del cartón.
        Usado para regenerar cartones ya creados.
        """
        img = Image.open(ruta_imagen).convert('RGB')
        img = self._superponer_numero(img, numero)
        img.save(ruta_imagen, 'JPEG', quality=88)

    # ── procesamiento de página ───────────────────────────────────────────────

    def _procesar_pagina(self, pdf_path: str, indice: int,
                         carpeta_salida: str, ext: str) -> dict:
        """
        Renderiza la página del PDF y superpone el número del cartón
        en el óvalo dorado de la esquina superior derecha.
        """
        try:
            zoom   = self.dpi / 72.0
            matriz = fitz.Matrix(zoom, zoom)

            doc = fitz.open(pdf_path)
            try:
                page   = doc.load_page(indice)
                texto  = page.get_text()
                pix    = page.get_pixmap(matrix=matriz, alpha=False)
            finally:
                doc.close()

            # Número del cartón
            numero = self._extraer_numero_de_texto(texto)
            if not numero:
                numero = f'sin_numero_pagina_{indice + 1}'

            # Convertir pixmap a PIL Image
            img = Image.frombytes('RGB', [pix.width, pix.height], pix.samples)

            # Superponer "Nro # XXXXXX" en el óvalo dorado
            img = self._superponer_numero(img, numero)

            # Guardar
            ruta_destino = os.path.join(carpeta_salida, f'{numero}.{ext}')
            if os.path.exists(ruta_destino):
                contador = 2
                while True:
                    alt = os.path.join(carpeta_salida, f'{numero}_{contador}.{ext}')
                    if not os.path.exists(alt):
                        ruta_destino = alt
                        break
                    contador += 1

            os.makedirs(carpeta_salida, exist_ok=True)
            img.save(ruta_destino, 'JPEG', quality=88)

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
