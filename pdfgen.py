"""Gerador de PDF mínimo (sem dependências) para os relatórios de impressão.

Usa as fontes padrão do PDF (Helvetica), que não precisam ser embutidas,
com codificação WinAnsi (cp1252): cobre os acentos do português.
Coordenadas em pontos, com origem no canto SUPERIOR esquerdo.
"""

import zlib

A4 = (595.28, 841.89)
A4_LANDSCAPE = (841.89, 595.28)

# Larguras (1/1000 do tamanho) dos caracteres cp1252 32..255.
_W_REGULAR = [278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278, 556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 278, 278, 584, 584, 584, 556, 1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778, 667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556, 333, 556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556, 556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584, 761, 556, 0, 222, 556, 333, 1000, 556, 556, 333, 1000, 667, 333, 1000, 0, 611, 0, 0, 222, 222, 333, 333, 350, 556, 1000, 333, 1000, 500, 333, 944, 0, 500, 667, 278, 333, 556, 556, 556, 556, 260, 556, 333, 737, 370, 556, 584, 333, 737, 333, 400, 584, 333, 333, 333, 556, 537, 278, 333, 333, 365, 556, 834, 834, 834, 611, 667, 667, 667, 667, 667, 667, 1000, 722, 667, 667, 667, 667, 278, 278, 278, 278, 722, 722, 778, 778, 778, 778, 778, 584, 778, 722, 722, 722, 722, 667, 667, 611, 556, 556, 556, 556, 556, 556, 889, 500, 556, 556, 556, 556, 278, 278, 278, 278, 556, 556, 556, 556, 556, 556, 556, 584, 611, 556, 556, 556, 556, 500, 556, 500]  # noqa: E501
_W_BOLD = [278, 333, 474, 556, 556, 889, 722, 238, 333, 333, 389, 584, 278, 333, 278, 278, 556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 333, 333, 584, 584, 584, 611, 975, 722, 722, 722, 722, 667, 611, 778, 722, 278, 556, 722, 611, 833, 722, 778, 667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 333, 278, 333, 584, 556, 333, 556, 611, 556, 611, 556, 333, 611, 611, 278, 278, 556, 278, 889, 611, 611, 611, 611, 389, 556, 333, 611, 556, 778, 556, 556, 500, 389, 280, 389, 584, 761, 556, 0, 278, 556, 500, 1000, 556, 556, 333, 1000, 667, 333, 1000, 0, 611, 0, 0, 278, 278, 500, 500, 350, 556, 1000, 333, 1000, 556, 333, 944, 0, 500, 667, 278, 333, 556, 556, 556, 556, 280, 556, 333, 737, 370, 556, 584, 333, 737, 333, 400, 584, 333, 333, 333, 611, 556, 278, 333, 333, 365, 556, 834, 834, 834, 611, 722, 722, 722, 722, 722, 722, 1000, 722, 667, 667, 667, 667, 278, 278, 278, 278, 722, 722, 778, 778, 778, 778, 778, 584, 778, 722, 722, 722, 722, 667, 667, 611, 556, 556, 556, 556, 556, 556, 889, 556, 556, 556, 556, 556, 278, 278, 278, 278, 611, 611, 611, 611, 611, 611, 611, 584, 611, 611, 611, 611, 611, 556, 611, 556]  # noqa: E501
_FONTS = {"F1": ("Helvetica", _W_REGULAR), "F2": ("Helvetica-Bold", _W_BOLD)}


def _encode(text):
    return str(text).encode("cp1252", errors="replace")


def text_width(text, size, bold=False):
    widths = _W_BOLD if bold else _W_REGULAR
    total = 0
    for byte in _encode(text):
        total += widths[byte - 32] if 32 <= byte <= 255 else 500
    return total * size / 1000.0


def wrap(text, size, width, bold=False):
    """Quebra o texto em linhas que cabem na largura."""
    lines = []
    for paragraph in str(text).split("\n"):
        line = ""
        for word in paragraph.split(" "):
            candidate = (line + " " + word) if line else word
            if text_width(candidate, size, bold) <= width or not line:
                line = candidate
            else:
                lines.append(line)
                line = word
        lines.append(line)
    return lines


def fit(text, size, width, bold=False):
    """Corta com "…" se não couber."""
    text = str(text)
    if text_width(text, size, bold) <= width:
        return text
    while text and text_width(text + "...", size, bold) > width:
        text = text[:-1]
    return text + "..."


def _rgb(color):
    """"#RRGGBB" -> "r g b" (0..1)."""
    color = color.lstrip("#")
    return " ".join("{:.3f}".format(int(color[i:i + 2], 16) / 255.0) for i in (0, 2, 4))


def _pdf_string(text):
    raw = _encode(text)
    raw = raw.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")
    return b"(" + raw + b")"


class PDF:
    def __init__(self, pagesize=A4, title="", author=""):
        self.width, self.height = pagesize
        self.title = title
        self.author = author
        self.pages = []
        self._ops = None

    # --- páginas -------------------------------------------------------
    def add_page(self):
        self._ops = []
        self.pages.append(self._ops)

    @property
    def page_number(self):
        return len(self.pages)

    def _y(self, y):
        return self.height - y

    # --- desenho -------------------------------------------------------
    def rect(self, x, y, w, h, fill=None, stroke=None, line_width=0.6, radius=0):
        """Retângulo com topo em y (opcionalmente arredondado)."""
        ops = ["q"]
        if fill:
            ops.append(_rgb(fill) + " rg")
        if stroke:
            ops.append(_rgb(stroke) + " RG {:.2f} w".format(line_width))
        bottom = self._y(y + h)
        if radius:
            r = min(radius, w / 2.0, h / 2.0)
            k = r * 0.5523
            x0, y0, x1, y1 = x, bottom, x + w, bottom + h
            ops.append(
                "{:.2f} {:.2f} m {:.2f} {:.2f} l "
                "{:.2f} {:.2f} {:.2f} {:.2f} {:.2f} {:.2f} c "
                "{:.2f} {:.2f} l "
                "{:.2f} {:.2f} {:.2f} {:.2f} {:.2f} {:.2f} c "
                "{:.2f} {:.2f} l "
                "{:.2f} {:.2f} {:.2f} {:.2f} {:.2f} {:.2f} c "
                "{:.2f} {:.2f} l "
                "{:.2f} {:.2f} {:.2f} {:.2f} {:.2f} {:.2f} c h".format(
                    x0 + r, y0, x1 - r, y0,
                    x1 - r + k, y0, x1, y0 + r - k, x1, y0 + r,
                    x1, y1 - r,
                    x1, y1 - r + k, x1 - r + k, y1, x1 - r, y1,
                    x0 + r, y1,
                    x0 + r - k, y1, x0, y1 - r + k, x0, y1 - r,
                    x0, y0 + r,
                    x0, y0 + r - k, x0 + r - k, y0, x0 + r, y0))
        else:
            ops.append("{:.2f} {:.2f} {:.2f} {:.2f} re".format(x, bottom, w, h))
        ops.append("B" if fill and stroke else ("f" if fill else "S"))
        ops.append("Q")
        self._ops.append(" ".join(ops).encode("ascii"))

    def line(self, x1, y1, x2, y2, color="#000000", width=0.6, dash=None):
        dash_op = "[{} {}] 0 d ".format(*dash) if dash else ""
        self._ops.append("q {} RG {:.2f} w {}{:.2f} {:.2f} m {:.2f} {:.2f} l S Q".format(
            _rgb(color), width, dash_op, x1, self._y(y1), x2, self._y(y2)).encode("ascii"))

    def text(self, x, y, text, size=10, bold=False, color="#000000", align="left"):
        """Texto com a linha de base em y. align: left/center/right (x é a âncora)."""
        if align != "left":
            w = text_width(text, size, bold)
            x = x - w / 2.0 if align == "center" else x - w
        self._ops.append(b"BT /" + (b"F2" if bold else b"F1")
                         + " {:.2f} Tf {} rg {:.2f} {:.2f} Td ".format(
                             size, _rgb(color), x, self._y(y)).encode("ascii")
                         + _pdf_string(text) + b" Tj ET")

    def text_in_box(self, x, y, w, h, text, size=9, bold=False, color="#000000",
                    align="center", padding=3, line_gap=1.15):
        """Texto quebrado e centralizado verticalmente dentro da caixa."""
        lines = wrap(text, size, w - 2 * padding, bold)
        max_lines = max(1, int((h - 2) // (size * line_gap)))
        lines = lines[:max_lines]
        lines[-1] = fit(lines[-1], size, w - 2 * padding, bold)
        block = len(lines) * size * line_gap
        base = y + (h - block) / 2.0 + size * 0.85
        for i, line in enumerate(lines):
            ly = base + i * size * line_gap
            if align == "center":
                self.text(x + w / 2.0, ly, line, size, bold, color, "center")
            elif align == "right":
                self.text(x + w - padding, ly, line, size, bold, color, "right")
            else:
                self.text(x + padding, ly, line, size, bold, color)

    # --- arquivo -------------------------------------------------------
    def output(self, path):
        objects = []  # bytes de cada objeto (1-based)

        def add(obj):
            objects.append(obj)
            return len(objects)

        catalog = add(b"")  # preenchido depois
        pages_id = add(b"")
        font_ids = {}
        for key, (name, _w) in _FONTS.items():
            font_ids[key] = add(
                "<< /Type /Font /Subtype /Type1 /BaseFont /{} "
                "/Encoding /WinAnsiEncoding >>".format(name).encode("ascii"))
        resources = "<< /Font << {} >> >>".format(
            " ".join("/{} {} 0 R".format(k, v) for k, v in font_ids.items()))
        page_ids = []
        for ops in self.pages:
            data = zlib.compress(b"\n".join(ops))
            content = add(b"<< /Length " + str(len(data)).encode() + b" /Filter /FlateDecode >>\nstream\n"
                          + data + b"\nendstream")
            page_ids.append(add(
                "<< /Type /Page /Parent {} 0 R /MediaBox [0 0 {:.2f} {:.2f}] "
                "/Resources {} /Contents {} 0 R >>".format(
                    pages_id, self.width, self.height, resources, content).encode("ascii")))
        objects[pages_id - 1] = "<< /Type /Pages /Kids [{}] /Count {} >>".format(
            " ".join("{} 0 R".format(p) for p in page_ids), len(page_ids)).encode("ascii")
        objects[catalog - 1] = "<< /Type /Catalog /Pages {} 0 R >>".format(pages_id).encode("ascii")
        info = add(b"<< /Title " + _pdf_string(self.title) + b" /Author " + _pdf_string(self.author)
                   + b" /Producer (Material Circulante) >>")

        out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = []
        for i, obj in enumerate(objects, start=1):
            offsets.append(len(out))
            out += "{} 0 obj\n".format(i).encode("ascii") + obj + b"\nendobj\n"
        xref = len(out)
        out += "xref\n0 {}\n0000000000 65535 f \n".format(len(objects) + 1).encode("ascii")
        for off in offsets:
            out += "{:010d} 00000 n \n".format(off).encode("ascii")
        out += ("trailer\n<< /Size {} /Root {} 0 R /Info {} 0 R >>\nstartxref\n{}\n%%EOF\n".format(
            len(objects) + 1, catalog, info, xref)).encode("ascii")
        with open(path, "wb") as fh:
            fh.write(out)
        return path
