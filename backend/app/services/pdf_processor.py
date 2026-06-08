"""Servicio de procesamiento de PDF.
Extrae números del cartón desde el PDF y los compone sobre la plantilla
carton_final_ref.jpeg para generar imágenes portrait con header + grilla BINGO.
"""
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional

import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont

# ── constantes de posición ────────────────────────────────────────────────────

# Posición del óvalo dorado calibrada sobre carton_final_ref.jpeg
OVALO_CX = 0.775   # centro X como fracción del ancho
OVALO_CY = 0.128   # centro Y como fracción del alto

# Área de borrado dentro del óvalo (para tapar el número anterior de la plantilla)
OVALO_CLEAR_HW = 0.210  # semi-ancho como fracción del ancho de la imagen
OVALO_CLEAR_HH = 0.072  # semi-alto  como fracción del alto  de la imagen
OVALO_BG_COLOR = '#D4A84B'  # color interior aproximado del óvalo dorado

# Proporciones de la grilla (fracción del alto total de la plantilla)
GRID_TOP      = 0.280   # donde empieza la grilla (bajo el header)
BINGO_ROW_H   = 0.119   # altura de la fila B/I/N/G/O
NUM_ROW_H     = 0.108   # altura de cada fila de números (×5)
# Las 5 filas de números van desde GRID_TOP+BINGO_ROW_H hasta ~0.94 del alto

# Plantilla portrait con header + estructura de grilla vacía
_TEMPLATE_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'static', 'carton_final_ref.jpeg'
)

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

# Cache thread-safe de la plantilla base
_template_cache: Optional[Image.Image] = None
_template_lock = threading.Lock()


def _cargar_plantilla() -> Optional[Image.Image]:
    global _template_cache
    with _template_lock:
        if _template_cache is None:
            if os.path.isfile(_TEMPLATE_PATH):
                _template_cache = Image.open(_TEMPLATE_PATH).convert('RGB')
                print(f'[BINGO] Plantilla cargada: {_TEMPLATE_PATH} {_template_cache.size}', flush=True)
            else:
                print(f'[BINGO] AVISO: plantilla no encontrada: {_TEMPLATE_PATH}', flush=True)
    return _template_cache


# ── clases ────────────────────────────────────────────────────────────────────

class PDFProcessorError(Exception):
    pass


class PDFProcessor:
    REGEX_NUMERO        = re.compile(r'^\s*(\d{3,8})\s*$')
    REGEX_NUMERO_INLINE = re.compile(r'\b(\d{3,8})\b')

    def __init__(self, dpi: int = 72, formato: str = 'jpeg'):
        self.dpi     = dpi
        self.formato = formato.lower()
        if self.formato not in ('jpeg', 'png'):
            raise ValueError("formato debe ser 'jpeg' o 'png'")
        print(f'[BINGO] PDFProcessor init: dpi={dpi} fuente={FONT_PATH}', flush=True)

    # ── extracción de texto ───────────────────────────────────────────────────

    def _extraer_numero_carton(self, texto: str) -> Optional[str]:
        """Extrae el número de cartón (número grande, > 75) del texto del PDF."""
        lines = [l.strip() for l in texto.split('\n') if l.strip()]
        if not lines:
            return None
        # Busca el último número de 3-8 dígitos
        m = self.REGEX_NUMERO.match(lines[-1])
        if m:
            return m.group(1)
        for line in reversed(lines[-3:]):
            m = self.REGEX_NUMERO_INLINE.search(line)
            if m:
                return m.group(1)
        return None

    def _extraer_grid_bingo(self, texto: str) -> dict:
        """
        Extrae los 25 números de la grilla BINGO del texto del PDF.
        Retorna {'B': [5], 'I': [5], 'N': [5 con None en centro], 'G': [5], 'O': [5]}.
        """
        # Todos los números 1-75 en orden de aparición, sin duplicados
        vistos: set = set()
        nums: list = []
        for m in re.finditer(r'\b(\d{1,2})\b', texto):
            n = int(m.group(1))
            if 1 <= n <= 75 and n not in vistos:
                vistos.add(n)
                nums.append(n)

        B      = [n for n in nums if  1 <= n <= 15][:5]
        I      = [n for n in nums if 16 <= n <= 30][:5]
        N_list = [n for n in nums if 31 <= n <= 45][:4]
        G      = [n for n in nums if 46 <= n <= 60][:5]
        O      = [n for n in nums if 61 <= n <= 75][:5]

        # Completar con ceros si faltan números
        while len(B) < 5:      B.append(0)
        while len(I) < 5:      I.append(0)
        while len(N_list) < 4: N_list.append(0)
        while len(G) < 5:      G.append(0)
        while len(O) < 5:      O.append(0)

        # Columna N: None en posición central (índice 2)
        N = N_list[:2] + [None] + N_list[2:]

        return {'B': B, 'I': I, 'N': N, 'G': G, 'O': O}

    # ── dibujo de celdas ─────────────────────────────────────────────────────

    def _fuente(self, size: int) -> ImageFont.ImageFont:
        if FONT_PATH:
            try:
                return ImageFont.truetype(FONT_PATH, size)
            except Exception:
                pass
        return ImageFont.load_default()

    def _draw_numero_celda(self, draw: ImageDraw.ImageDraw,
                           cx: int, cy: int, texto: str, row_h: int) -> None:
        """Dibuja un número grande centrado en la celda."""
        size = max(14, int(row_h * 0.60))
        font = self._fuente(size)
        bbox = draw.textbbox((0, 0), texto, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.text((cx - tw // 2, cy - th // 2), texto, fill='#1a1a1a', font=font)

    def _draw_celda_central(self, draw: ImageDraw.ImageDraw,
                            cx: int, cy: int, numero: str, row_h: int) -> None:
        """Celda central N: 'TABLA NO.' arriba y número de cartón abajo."""
        size_label = max(8, int(row_h * 0.22))
        size_num   = max(10, int(row_h * 0.28))
        font_l = self._fuente(size_label)
        font_n = self._fuente(size_num)

        label = 'TABLA NO.'
        bbox_l = draw.textbbox((0, 0), label,  font=font_l)
        bbox_n = draw.textbbox((0, 0), numero, font=font_n)
        lw = bbox_l[2] - bbox_l[0];  lh = bbox_l[3] - bbox_l[1]
        nw = bbox_n[2] - bbox_n[0];  nh = bbox_n[3] - bbox_n[1]

        gap     = max(2, int(row_h * 0.06))
        total_h = lh + gap + nh
        top     = cy - total_h // 2

        draw.text((cx - lw // 2, top),            label,  fill='#666666', font=font_l)
        draw.text((cx - nw // 2, top + lh + gap), numero, fill='#333333', font=font_n)

    # ── composición del cartón ────────────────────────────────────────────────

    def _componer_carton(self, grid: dict, numero: str) -> Image.Image:
        """
        Carga la plantilla portrait (carton_final_ref.jpeg), borra los números
        existentes celda por celda y dibuja los nuevos.
        """
        plantilla = _cargar_plantilla()
        if plantilla is None:
            raise PDFProcessorError('Plantilla carton_final_ref.jpeg no encontrada en static/')

        img  = plantilla.copy()
        draw = ImageDraw.Draw(img)
        W, H = img.size

        grid_top    = int(H * GRID_TOP)
        bingo_row_h = int(H * BINGO_ROW_H)
        num_row_h   = int(H * NUM_ROW_H)
        col_w       = W // 5

        cols = ['B', 'I', 'N', 'G', 'O']

        for ci, col in enumerate(cols):
            numeros_col = grid.get(col, [0] * 5)
            x0 = ci * col_w
            x1 = x0 + col_w

            for ri in range(5):
                y0 = grid_top + bingo_row_h + ri * num_row_h
                y1 = y0 + num_row_h

                # Margen interior para no borrar los bordes de la celda
                margen_x = max(4, col_w  // 10)
                margen_y = max(4, num_row_h // 8)

                # Borrar número anterior con rectángulo blanco
                draw.rectangle(
                    [x0 + margen_x, y0 + margen_y, x1 - margen_x, y1 - margen_y],
                    fill='white'
                )

                cx = (x0 + x1) // 2
                cy = (y0 + y1) // 2

                if ci == 2 and ri == 2:
                    # Celda central: TABLA NO. + número de cartón
                    self._draw_celda_central(draw, cx, cy, numero, num_row_h)
                else:
                    val = numeros_col[ri] if ri < len(numeros_col) else 0
                    if val:
                        self._draw_numero_celda(draw, cx, cy, str(val), num_row_h)

        # Superponer "Nro # XXXXXX" en el óvalo dorado
        img = self._superponer_numero(img, numero)
        return img

    def _superponer_numero(self, img: Image.Image, numero: str) -> Image.Image:
        """
        Superpone 'Nro #' y el número del cartón en el círculo dorado
        de la esquina superior derecha (calibrado sobre carton_final_ref.jpeg).
        """
        draw = ImageDraw.Draw(img)
        W, H = img.size

        cx = int(W * OVALO_CX)
        cy = int(H * OVALO_CY)

        # Borrar el número anterior de la plantilla
        hw = int(W * OVALO_CLEAR_HW)
        hh = int(H * OVALO_CLEAR_HH)
        draw.rectangle([cx - hw, cy - hh, cx + hw, cy + hh], fill=OVALO_BG_COLOR)

        max_ancho = int(W * 0.32)

        font_num   = None
        font_label = None
        size_num   = 10

        if FONT_PATH:
            size_num = int(W * 0.11)
            while size_num >= 10:
                try:
                    f    = ImageFont.truetype(FONT_PATH, size_num)
                    bbox = draw.textbbox((0, 0), numero, font=f)
                    if (bbox[2] - bbox[0]) <= max_ancho:
                        font_num = f
                        break
                except Exception:
                    pass
                size_num -= 1

            size_label = max(8, size_num // 3)
            try:
                font_label = ImageFont.truetype(FONT_PATH, size_label)
            except Exception:
                font_label = None

        if font_num is None:
            font_num = ImageFont.load_default()
        if font_label is None:
            font_label = ImageFont.load_default()

        bbox_label = draw.textbbox((0, 0), 'Nro #', font=font_label)
        lw = bbox_label[2] - bbox_label[0]
        lh = bbox_label[3] - bbox_label[1]

        bbox_num = draw.textbbox((0, 0), numero, font=font_num)
        nw = bbox_num[2] - bbox_num[0]
        nh = bbox_num[3] - bbox_num[1]

        gap       = max(2, int(H * 0.006))
        total_h   = lh + gap + nh
        block_top = cy - total_h // 2

        lx = cx - lw // 2
        ly = block_top
        nx = cx - nw // 2
        ny = block_top + lh + gap

        draw.text((lx + 1, ly + 1), 'Nro #', fill='#aaaaaa', font=font_label)
        draw.text((lx,     ly    ), 'Nro #', fill='#666666', font=font_label)

        sombra = max(1, size_num // 25) if FONT_PATH else 1
        draw.text((nx + sombra, ny + sombra), numero, fill='#333333', font=font_num)
        draw.text((nx,          ny          ), numero, fill='#0d0d0d', font=font_num)

        return img

    # ── procesamiento de página ───────────────────────────────────────────────

    def _procesar_pagina(self, pdf_path: str, indice: int,
                         carpeta_salida: str, ext: str,
                         ruta_destino_override: Optional[str] = None) -> dict:
        """
        Extrae los datos del PDF y genera la imagen portrait del cartón:
        header decorativo + grilla BINGO con números reales.
        """
        try:
            doc = fitz.open(pdf_path)
            try:
                page  = doc.load_page(indice)
                texto = page.get_text()
            finally:
                doc.close()

            numero = self._extraer_numero_carton(texto)
            if not numero:
                numero = f'sin_numero_pagina_{indice + 1}'

            grid = self._extraer_grid_bingo(texto)

            # Componer imagen portrait con plantilla + números
            img = self._componer_carton(grid, numero)

            # Determinar ruta de destino
            if ruta_destino_override:
                ruta_destino = ruta_destino_override
            else:
                ruta_destino = os.path.join(carpeta_salida, f'{numero}.{ext}')
                if os.path.exists(ruta_destino):
                    contador = 2
                    while True:
                        alt = os.path.join(carpeta_salida, f'{numero}_{contador}.{ext}')
                        if not os.path.exists(alt):
                            ruta_destino = alt
                            break
                        contador += 1

            os.makedirs(os.path.dirname(ruta_destino) if ruta_destino_override
                        else carpeta_salida, exist_ok=True)
            img.save(ruta_destino, 'JPEG', quality=90)

            return {
                'ok':    {'indice': indice, 'numero': numero,
                          'pagina': indice + 1, 'ruta': ruta_destino},
                'error': None,
            }
        except Exception as ex:
            import traceback
            print(f'[BINGO] ERROR pagina {indice}: {ex}\n{traceback.format_exc()}', flush=True)
            return {
                'ok':    None,
                'error': {'indice': indice, 'numero': None, 'razon': str(ex)},
            }

    # ── regeneración de cartón existente ─────────────────────────────────────

    def regenerar_desde_pdf(self, pdf_path: str, pagina_origen: int,
                            ruta_imagen: str, numero: str) -> None:
        """
        Regenera la imagen de un cartón procesando nuevamente la página del PDF.
        pagina_origen es 1-based (como está guardado en la BD).
        """
        if not os.path.isfile(pdf_path):
            raise PDFProcessorError(f'PDF no encontrado: {pdf_path}')
        ext = 'jpg' if self.formato == 'jpeg' else 'png'
        resultado = self._procesar_pagina(
            pdf_path, pagina_origen - 1,
            os.path.dirname(ruta_imagen), ext,
            ruta_destino_override=ruta_imagen,
        )
        if resultado['error']:
            raise PDFProcessorError(resultado['error']['razon'])

    def superponer_numero_en_archivo(self, ruta_imagen: str, numero: str) -> None:
        """
        Fallback: superpone el número en una imagen existente (sin PDF).
        Usado solo cuando el PDF original no está disponible.
        """
        img = Image.open(ruta_imagen).convert('RGB')
        img = self._superponer_numero(img, numero)
        img.save(ruta_imagen, 'JPEG', quality=90)

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
