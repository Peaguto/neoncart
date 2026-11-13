"""Relatórios em PDF (para imprimir) das pastas do Porta Vasos."""

from datetime import datetime

import portavasos as pv
from pdfgen import A4_LANDSCAPE, PDF, fit, text_width
from pdfgen import wrap as wrap_lines

NAVY = "#1F4E78"
BLUE = "#2F75B5"
LIGHT = "#EAF1F8"
ZEBRA = "#F6F9FC"
BORDER = "#C9D6E3"
INK = "#1E293B"
MUTED = "#64748B"
WHITE = "#FFFFFF"
STATUS_COLORS = {
    pv.WAITING: ("#B45309", "#FEF3C7"),   # âmbar
    pv.RETURNED: ("#15803D", "#DCFCE7"),  # verde
}

MARGIN = 28
ROW_H = 20
HEAD_H = 30
FOOTER_SPACE = 46


class _Report:
    def __init__(self, title):
        self.pdf = PDF(A4_LANDSCAPE, title=title, author="Material Circulante")
        self.w = self.pdf.width
        self.h = self.pdf.height
        self.footers = []  # (página, texto central)
        self.generated = datetime.now().strftime("%d/%m/%Y %H:%M")

    @property
    def bottom(self):
        return self.h - FOOTER_SPACE

    def new_page(self, label):
        self.pdf.add_page()
        self.footers.append(label)

    # --- blocos --------------------------------------------------------
    def status_pill(self, x_right, y, status, size=9):
        fg, bg = STATUS_COLORS[status]
        label = pv.STATUS_LABELS[status]
        w = text_width(label, size, True) + 26
        x = x_right - w
        self.pdf.rect(x, y, w, 22, fill=bg, stroke=fg, line_width=0.8, radius=11)
        self.pdf.rect(x + 9, y + 8, 6, 6, fill=fg, radius=3)
        self.pdf.text(x + 19, y + 14.6, label, size, True, fg)
        return w

    def banner(self, subtitle, status=None):
        p = self.pdf
        p.rect(MARGIN, MARGIN, self.w - 2 * MARGIN, 56, fill=NAVY, radius=8)
        p.text(MARGIN + 18, MARGIN + 25, "CONTROLE DE MATERIAL CIRCULANTE", 17, True, WHITE)
        p.text(MARGIN + 18, MARGIN + 42, subtitle, 9, False, "#BFD3E6")
        if status:
            self.status_pill(self.w - MARGIN - 16, MARGIN + 17, status)
        return MARGIN + 56 + 12

    def info_cards(self, y, cards):
        """cards: [(rótulo, valor, peso)]"""
        gap = 8
        total_w = self.w - 2 * MARGIN - gap * (len(cards) - 1)
        weight = float(sum(c[2] for c in cards))
        x = MARGIN
        for label, value, wgt in cards:
            w = total_w * wgt / weight
            self.pdf.rect(x, y, w, 44, fill=LIGHT, stroke=BORDER, radius=6)
            self.pdf.text(x + 10, y + 15, label, 7, True, MUTED)
            self.pdf.text(x + 10, y + 33, fit(value, 13, w - 20, True), 13, True, INK)
            x += w + gap
        return y + 44 + 12

    def table_header(self, y, columns):
        x = MARGIN
        for title, w, _align in columns:
            size = 7.0
            longest = max(title.split(" "), key=lambda word: text_width(word, size, True))
            while size > 5 and text_width(longest, size, True) > w - 6:
                size -= 0.25
            self.pdf.rect(x, y, w, HEAD_H, fill=BLUE, stroke=WHITE, line_width=0.8)
            self.pdf.text_in_box(x, y, w, HEAD_H, title, size, True, WHITE)
            x += w
        return y + HEAD_H

    def table_row(self, y, columns, values, fill=None, bold=False, color=INK):
        x = MARGIN
        for (title, w, align), value in zip(columns, values):
            self.pdf.rect(x, y, w, ROW_H, fill=fill or WHITE, stroke=BORDER, line_width=0.5)
            if value not in (None, ""):
                self.pdf.text_in_box(x, y, w, ROW_H, str(value), 9, bold, color, align, padding=6)
            x += w
        return y + ROW_H

    def footer_all(self):
        total = len(self.pdf.pages)
        for i, label in enumerate(self.footers):
            self.pdf._ops = self.pdf.pages[i]
            y = self.h - 30
            self.pdf.line(MARGIN, y - 10, self.w - MARGIN, y - 10, BORDER, 0.6)
            self.pdf.text(MARGIN, y, "Material Circulante · Porta Vasos", 8, True, MUTED)
            self.pdf.text(self.w / 2.0, y, fit(label, 8, 300), 8, False, MUTED, "center")
            self.pdf.text(self.w - MARGIN, y, "Gerado em {}   ·   Página {} de {}".format(
                self.generated, i + 1, total), 8, False, MUTED, "right")


# --- pasta ---------------------------------------------------------------
def _folder_columns(records, avail):
    items = pv.used_items(records)
    fixed = [("Nº", 26, "center"), ("DATA DE DEVOLUÇÃO", 70, "center")]
    total_col = ("TOTAL", 48, "center")
    fixed_w = sum(c[1] for c in fixed) + total_col[1]
    item_w = 0
    if items:
        item_w = max(34.0, min(66.0, (avail - fixed_w - 160) / len(items)))
    client_w = avail - fixed_w - item_w * len(items)
    columns = [fixed[0], ("CLIENTE", client_w, "left"), fixed[1]]
    columns += [(name, item_w, "center") for name in items]
    columns.append(total_col)
    return columns, items


def _draw_folder(rep, folder):
    records = pv.sort_records(folder["records"])
    by_client = pv.totals_by_client(records)
    sums, total = pv.totals(records)
    label = "{}  ·  {}".format(folder["name"], pv.period_text(folder))

    rep.new_page(label)
    y = rep.banner("PORTA VASOS  ·  DEVOLUÇÃO DE MATERIAL", folder["status"])
    cards = [("PASTA", folder["name"], 3), ("PERÍODO", pv.period_text(folder), 2.4),
             ("CLIENTES", str(len(by_client)), 1), ("TOTAL DE ITENS", str(total), 1.2)]
    if folder["status"] == pv.RETURNED and folder["status_date"]:
        cards.append(("DEVOLVIDO EM", pv.format_date(folder["status_date"][:10]), 1.4))
    y = rep.info_cards(y, cards)

    columns, items = _folder_columns(records, rep.w - 2 * MARGIN)
    y = rep.table_header(y, columns)
    if not records:
        width = sum(c[1] for c in columns)
        rep.pdf.rect(MARGIN, y, width, 34, fill=WHITE, stroke=BORDER)
        rep.pdf.text(MARGIN + width / 2.0, y + 21, "Nenhum cliente registrado nesta pasta.",
                     10, False, MUTED, "center")
        y += 34
    for n, r in enumerate(records, start=1):
        if y + ROW_H > rep.bottom:
            rep.new_page(label)
            rep.pdf.text(MARGIN, MARGIN + 12, "{} (continuação)".format(folder["name"]),
                         11, True, NAVY)
            y = rep.table_header(MARGIN + 22, columns)
        values = [n, r["client"], pv.format_date(r["date"])]
        values += [r["items"].get(name) or "" for name in items]
        values.append(pv.record_total(r))
        y = rep.table_row(y, columns, values, fill=ZEBRA if n % 2 == 0 else WHITE)
    if records:
        if y + ROW_H > rep.bottom:
            rep.new_page(label)
            y = rep.table_header(MARGIN, columns)
        values = ["", "TOTAL DA PASTA", ""] + [sums[name] or "" for name in items] + [total]
        y = rep.table_row(y, columns, values, fill=LIGHT, bold=True, color=NAVY)

    # Resumo por cliente + conferência
    block_h = 34 + ROW_H * max(1, len(by_client))
    if y + 18 + min(block_h, 120) > rep.bottom:
        rep.new_page(label)
        y = MARGIN
    else:
        y += 18
    left_w = 420
    cols = [("CLIENTE", 130, "left"), ("DEVOLUÇÕES (DATA E ITENS)", left_w - 130 - 56, "left"),
            ("TOTAL", 56, "center")]
    rep.pdf.text(MARGIN, y + 10, "RESUMO POR CLIENTE", 9, True, NAVY)
    ty = rep.table_header(y + 16, cols) if by_client else y + 16
    for i, (client, recs, _sums, ctotal) in enumerate(pv.client_summary(records)):
        if ty + ROW_H > rep.bottom:
            rep.new_page(label)
            ty = rep.table_header(MARGIN, cols)
        days = " + ".join("{} ({})".format(pv.format_date(r["date"], short=True),
                                           pv.record_total(r)) for r in recs)
        ty = rep.table_row(ty, cols, [client, days, ctotal], fill=ZEBRA if i % 2 else WHITE,
                           bold=len(recs) > 1)
    if not by_client:
        rep.pdf.text(MARGIN, ty + 12, "-", 9, False, MUTED)

    # Códigos dos carrinhos
    with_codes = [r for r in records if r.get("carts")]
    if with_codes:
        ty += 14
        rep.pdf.text(MARGIN, ty + 10, "CÓDIGOS DOS CARRINHOS", 9, True, NAVY)
        ty += 16
        for r in with_codes:
            line = "{} ({}): {}".format(r["client"], pv.format_date(r["date"], short=True),
                                        pv.carts_text(r))
            for part in wrap_lines(line, 8.5, left_w):
                if ty + 12 > rep.bottom:
                    rep.new_page(label)
                    ty = MARGIN
                rep.pdf.text(MARGIN, ty + 10, part, 8.5, False, INK)
                ty += 12

    # Assinaturas (ao lado do resumo, na primeira página do bloco)
    sx = MARGIN + left_w + 40
    sw = rep.w - MARGIN - sx
    rep.pdf.text(sx, y + 10, "CONFERÊNCIA", 9, True, NAVY)
    rep.pdf.rect(sx, y + 16, sw, 96, fill=WHITE, stroke=BORDER, radius=6)
    half = (sw - 48) / 2.0
    for i, caption in enumerate(("Conferido por (LOG)", "Responsável pela devolução")):
        lx = sx + 16 + i * (half + 16)
        rep.pdf.line(lx, y + 62, lx + half, y + 62, INK, 0.7)
        rep.pdf.text(lx, y + 74, caption, 8, False, MUTED)
    rep.pdf.text(sx + 16, y + 100, "Data: ____/____/________", 9, False, INK)


def _draw_cover(rep, folders, subtitle):
    rep.new_page("Relatório de pastas")
    y = rep.banner("PORTA VASOS  ·  RELATÓRIO DE PASTAS  ·  " + subtitle)
    waiting = sum(1 for f in folders if f["status"] == pv.WAITING)
    records = pv.all_records(folders)
    _, total = pv.totals(records)
    y = rep.info_cards(y, [
        ("PASTAS", str(len(folders)), 1), ("AGUARDANDO DEVOLUÇÃO", str(waiting), 1.4),
        ("DEVOLVIDAS", str(len(folders) - waiting), 1.2),
        ("CLIENTES", str(len(pv.totals_by_client(records))), 1),
        ("TOTAL DE ITENS", str(total), 1.2)])
    avail = rep.w - 2 * MARGIN
    columns = [("Nº", 26, "center"), ("PASTA", avail - 26 - 150 - 170 - 70 - 70, "left"),
               ("PERÍODO", 150, "center"), ("STATUS", 170, "center"),
               ("CLIENTES", 70, "center"), ("ITENS", 70, "center")]
    y = rep.table_header(y, columns)
    for n, f in enumerate(folders, start=1):
        if y + ROW_H > rep.bottom:
            rep.new_page("Relatório de pastas")
            y = rep.table_header(MARGIN, columns)
        fg, _bg = STATUS_COLORS[f["status"]]
        x_status = MARGIN + sum(c[1] for c in columns[:3])
        y_row = y
        y = rep.table_row(y, columns, [
            n, f["name"], pv.period_text(f), "", len(pv.totals_by_client(f["records"])),
            pv.folder_total(f)], fill=ZEBRA if n % 2 == 0 else WHITE)
        rep.pdf.text(x_status + 85, y_row + 13.5, pv.STATUS_LABELS[f["status"]], 8, True, fg,
                     "center")
    sums, total = pv.totals(records)
    rows = [(name, qty) for name, qty in sums.items() if qty]
    if rows:
        y += 18
        if y + 16 + HEAD_H + ROW_H > rep.bottom:
            rep.new_page("Relatório de pastas")
            y = MARGIN
        rep.pdf.text(MARGIN, y + 10, "TOTAL POR MATERIAL", 9, True, NAVY)
        cols = [(name, min(66.0, avail / len(rows)), "center") for name, _ in rows]
        hy = rep.table_header(y + 16, cols)
        rep.table_row(hy, cols, [qty for _, qty in rows], bold=True, color=NAVY)


def export_folders_pdf(folders, path, subtitle="TODAS AS PASTAS"):
    """PDF de uma pasta (1 item) ou de várias (com capa de resumo)."""
    title = folders[0]["name"] if len(folders) == 1 else "Pastas - Porta Vasos"
    rep = _Report(title)
    if len(folders) != 1:
        _draw_cover(rep, folders, subtitle)
    for folder in folders:
        _draw_folder(rep, folder)
    rep.footer_all()
    rep.pdf.output(path)
    return path
