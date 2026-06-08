"""Servicio de procesamiento de PDF.
Genera cartones portrait: logo_superior.jpeg como header +
grilla BINGO dibujada con los números extraídos del PDF.
"""
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional

import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont

# ── rutas ─────────────────────────────────────────────────────────────────────

_STATIC_DIR = os.path.join(os.path.dirname(__file__), '..', 'static')
_LOGO_PATH  = os.path.join(_STATIC_DIR, 'logo_superior.jpeg')

# ── posición del círculo dorado dentro del logo (fracciones del logo) ─────────
# El círculo grande está en el lado derecho de logo_superior.jpeg
CIRCULO_X = 0.805   # centro X del círculo como fracción del ancho del logo
CIRCULO_Y = 0.430   # centro Y del círculo como fracción del alto del logo

# ── parámetros de la grilla ───────────────────────────────────────────────────
# Ancho fijo del cartón en píxeles (el alto se calcula según el logo)
CARD_WIDTH = 620

# ── fuentes candidatas (Linux / Docker) ───────────────────────────────────────
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

# ── cache thread-safe del logo ────────────────────────────────────────────────
_logo_cache: Optional[Image.Image] = None
_logo_lock  = threading.Lock()


def _cargar_logo() -> Optional[Image.Image]:
    global _logo_cache
    with _logo_lock:
        if _logo_cache is None:
            if os.path.isfile(_LOGO_PATH):
                _logo_cache = Image.open(_LOGO_PATH).convert('RGB')
                print(f'[BINGO] Logo cargado: {_LOGO_PATH} {_logo_cache.size}', flush=True)
            else:
                print(f'[BINGO] AVISO: logo no encontrado en {_LOGO_PATH}', flush=True)
    return _logo_cache


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

    # ── utilidades de fuente ──────────────────────────────────────────────────

    def _fuente(self, size: int) -> ImageFont.ImageFont:
        if FONT_PATH:
            try:
                return ImageFont.truetype(FONT_PATH, size)
            except Exception:
                pass
        return ImageFont.load_default()

    # ── extracción de texto del PDF ───────────────────────────────────────────

    def _extraer_numero_carton(self, texto: str) -> Optional[str]:
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

    def _extraer_grid_bingo(self, texto: str) -> dict:
        """
        Extrae los 25 números de la grilla BINGO del texto del PDF.
        Retorna {'B':[5], 'I':[5], 'N':[5 con None en centro], 'G':[5], 'O':[5]}.
        """
        vistos: set = set()
        nums: list  = []
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

        while len(B)      < 5: B.append(0)
        while len(I)      < 5: I.append(0)
        while len(N_list) < 4: N_list.append(0)
        while len(G)      < 5: G.append(0)
        while len(O)      < 5: O.append(0)

        N = N_list[:2] + [None] + N_list[2:]
        return {'B': B, 'I': I, 'N': N, 'G': G, 'O': O}

    # ── dibujo de la grilla BINGO ─────────────────────────────────────────────

    def _dibujar_grilla(self, canvas: Image.Image, grid: dict,
                        numero: str, y_inicio: int) -> None:
        """Dibuja la grilla BINGO completa sobre el canvas a partir de y_inicio."""
        draw = ImageDraw.Draw(canvas)
        W    = canvas.width

        col_w       = W // 5
        cabecera_h  = int(col_w * 0.70)   # fila B/I/N/G/O
        celda_h     = int(col_w * 0.82)   # filas de números

        cols = ['B', 'I', 'N', 'G', 'O']
        COLOR_LINEA   = '#AAAAAA'
        COLOR_FONDO   = '#FFFFFF'
        COLOR_CABEC   = '#F0F0F0'
        COLOR_LETRA   = '#000000'
        COLOR_NUMERO  = '#111111'
        COLOR_CENTRAL = '#555555'

        total_grid_h = cabecera_h + 5 * celda_h

        # Fondo blanco de toda la grilla
        draw.rectangle([0, y_inicio, W, y_inicio + total_grid_h], fill=COLOR_FONDO)

        # ── fila cabecera B/I/N/G/O ───────────────────────────────────────────
        font_bingo = self._fuente(int(cabecera_h * 0.68))
        for ci, letra in enumerate(cols):
            x0 = ci * col_w
            x1 = x0 + col_w
            y0 = y_inicio
            y1 = y0 + cabecera_h
            draw.rectangle([x0, y0, x1, y1], fill=COLOR_CABEC)
            bbox = draw.textbbox((0, 0), letra, font=font_bingo)
            tw   = bbox[2] - bbox[0]
            th   = bbox[3] - bbox[1]
            draw.text(
                (x0 + (col_w - tw) // 2, y0 + (cabecera_h - th) // 2),
                letra, fill=COLOR_LETRA, font=font_bingo,
            )

        # ── celdas de números ─────────────────────────────────────────────────
        font_num     = self._fuente(int(celda_h * 0.58))
        font_central = self._fuente(int(celda_h * 0.22))
        font_ctabla  = self._fuente(int(celda_h * 0.18))

        for ci, col in enumerate(cols):
            nums_col = grid.get(col, [0] * 5)
            x0 = ci * col_w
            x1 = x0 + col_w

            for ri in range(5):
                y0 = y_inicio + cabecera_h + ri * celda_h
                y1 = y0 + celda_h
                cx = x0 + col_w  // 2
                cy = y0 + celda_h // 2

                draw.rectangle([x0, y0, x1, y1], fill=COLOR_FONDO)

                if ci == 2 and ri == 2:
                    # Celda central: TABLA NO. + número de cartón
                    label = 'TABLA NO.'
                    bl = draw.textbbox((0, 0), label,  font=font_ctabla)
                    bn = draw.textbbox((0, 0), numero, font=font_central)
                    lw = bl[2] - bl[0]; lh = bl[3] - bl[1]
                    nw = bn[2] - bn[0]; nh = bn[3] - bn[1]
                    gap     = max(2, int(celda_h * 0.05))
                    total_h = lh + gap + nh
                    top     = cy - total_h // 2
                    draw.text((cx - lw // 2, top),           label,  fill=COLOR_CENTRAL, font=font_ctabla)
                    draw.text((cx - nw // 2, top + lh + gap), numero, fill=COLOR_CENTRAL, font=font_central)
                else:
                    val = nums_col[ri] if ri < len(nums_col) else 0
                    if val:
                        txt  = str(val)
                        bbox = draw.textbbox((0, 0), txt, font=font_num)
                        tw   = bbox[2] - bbox[0]
                        th   = bbox[3] - bbox[1]
                        draw.text(
                            (cx - tw // 2, cy - th // 2),
                            txt, fill=COLOR_NUMERO, font=font_num,
                        )

        # ── líneas de la grilla ───────────────────────────────────────────────
        grid_bottom = y_inicio + total_grid_h
        # horizontales
        for ri in range(7):
            y = y_inicio + (cabecera_h if ri == 1 else
                            cabecera_h + (ri - 1) * celda_h if ri > 1 else 0)
            draw.line([(0, y), (W, y)], fill=COLOR_LINEA, width=2)
        draw.line([(0, grid_bottom), (W, grid_bottom)], fill=COLOR_LINEA, width=2)
        # verticales
        for ci in range(6):
            x = ci * col_w
            draw.line([(x, y_inicio), (x, grid_bottom)], fill=COLOR_LINEA, width=2)

    # ── superposición del número en el círculo del logo ───────────────────────

    def _superponer_numero(self, canvas: Image.Image, numero: str,
                           header_h: int) -> Image.Image:
        """
        Escribe 'Nro #' y el número del cartón dentro del círculo dorado
        del logo. La posición se calcula relativa al header real.
        """
        draw = ImageDraw.Draw(canvas)
        W    = canvas.width

        # Centro del círculo en el canvas portrait
        cx = int(W * CIRCULO_X)
        cy = int(header_h * CIRCULO_Y)

        # Ancho máximo disponible dentro del círculo (~38% del ancho del cartón)
        max_ancho = int(W * 0.28)

        # Tamaño adaptativo del número para que quepa en el círculo
        font_num   = None
        font_label = None
        size_num   = 10

        if FONT_PATH:
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
                size_num -= 1

            size_label = max(8, size_num // 3)
            try:
                font_label = ImageFont.truetype(FONT_PATH, size_label)
            except Exception:
                font_label = None

        if font_num   is None: font_num   = ImageFont.load_default()
        if font_label is None: font_label = ImageFont.load_default()

        # Medir textos
        bl = draw.textbbox((0, 0), 'Nro #', font=font_label)
        lw = bl[2] - bl[0];  lh = bl[3] - bl[1]
        bn = draw.textbbox((0, 0), numero,  font=font_num)
        nw = bn[2] - bn[0];  nh = bn[3] - bn[1]

        gap       = max(2, int(header_h * 0.008))
        total_h   = lh + gap + nh
        block_top = cy - total_h // 2

        lx = cx - lw // 2
        ly = block_top
        nx = cx - nw // 2
        ny = block_top + lh + gap

        # "Nro #" en gris oscuro con sombra sutil
        draw.text((lx + 1, ly + 1), 'Nro #', fill='#888888', font=font_label)
        draw.text((lx,     ly    ), 'Nro #', fill='#555555', font=font_label)

        # Número en negro con sombra
        sombra = max(1, size_num // 20) if FONT_PATH else 1
        draw.text((nx + sombra, ny + sombra), numero, fill='#444444', font=font_num)
        draw.text((nx,          ny          ), numero, fill='#0d0d0d', font=font_num)

        return canvas

    # ── composición del cartón completo ──────────────────────────────────────

    def _componer_carton(self, grid: dict, numero: str) -> Image.Image:
        """
        Crea la imagen portrait del cartón:
          1. logo_superior.jpeg como header (escalado a CARD_WIDTH)
          2. Grilla BINGO dibujada programáticamente
          3. Número del cartón en el círculo dorado del logo
        """
        logo = _cargar_logo()
        if logo is None:
            raise PDFProcessorError(
                'logo_superior.jpeg no encontrado en static/. '
                'Asegúrate de que el archivo esté en backend/app/static/'
            )

        # Escalar logo al ancho del cartón manteniendo proporción
        lw, lh = logo.size
        scale    = CARD_WIDTH / lw
        header_h = int(lh * scale)
        header   = logo.resize((CARD_WIDTH, header_h), Image.LANCZOS)

        # Calcular altura de la grilla
        col_w      = CARD_WIDTH // 5
        cabecera_h = int(col_w * 0.70)
        celda_h    = int(col_w * 0.82)
        grid_h     = cabecera_h + 5 * celda_h

        # Canvas portrait: logo arriba + grilla abajo
        total_h = header_h + grid_h
        canvas  = Image.new('RGB', (CARD_WIDTH, total_h), 'white')
        canvas.paste(header, (0, 0))

        # Dibujar grilla BINGO
        self._dibujar_grilla(canvas, grid, numero, header_h)

        # Escribir número en el círculo dorado del logo
        canvas = self._superponer_numero(canvas, numero, header_h)

        return canvas

    # ── procesamiento de página del PDF ──────────────────────────────────────

    def _procesar_pagina(self, pdf_path: str, indice: int,
                         carpeta_salida: str, ext: str,
                         ruta_destino_override: Optional[str] = None) -> dict:
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
            img  = self._componer_carton(grid, numero)

            if ruta_destino_override:
                ruta_destino = ruta_destino_override
                os.makedirs(os.path.dirname(ruta_destino), exist_ok=True)
            else:
                os.makedirs(carpeta_salida, exist_ok=True)
                ruta_destino = os.path.join(carpeta_salida, f'{numero}.{ext}')
                if os.path.exists(ruta_destino):
                    contador = 2
                    while True:
                        alt = os.path.join(carpeta_salida, f'{numero}_{contador}.{ext}')
                        if not os.path.exists(alt):
                            ruta_destino = alt
                            break
                        contador += 1

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
        """Regenera la imagen re-procesando la página original del PDF."""
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
        """Fallback: reconstruye el cartón desde la plantilla base."""
        logo = _cargar_logo()
        if logo is None:
            return
        img = Image.open(ruta_imagen).convert('RGB')
        # Si ya tiene el tamaño del cartón, solo reescribir el número
        lw, lh = logo.size
        scale    = CARD_WIDTH / lw
        header_h = int(lh * scale)
        img = self._superponer_numero(img, numero, header_h)
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
                        try:   carton_cb(resultado['ok'])
                        except Exception: pass
                else:
                    error.append(resultado['error'])
                    if error_cb:
                        try:   error_cb(resultado['error'])
                        except Exception: pass
                if progreso_cb:
                    try:   progreso_cb(len(ok) + len(error), total)
                    except Exception: pass

        ok.sort(key=lambda x: x['indice'])
        return {'ok': ok, 'error': error, 'total': total}
