"""Relatórios em Excel (.xlsx), backup e texto para compartilhar."""

import json
from collections import Counter
from datetime import datetime

from storage import ACTION_LABELS, local_datetime

HEADERS = ["DATA / HORA", "CÓDIGO DO CARRINHO", "DIVISÓRIA / SETOR", "OBSERVAÇÕES"]
HISTORY_HEADERS = ["DATA / HORA", "AÇÃO", "CÓDIGO", "DIVISÓRIA / SETOR", "ORIGEM"]
SOURCE_LABELS = {"camera": "Câmera", "manual": "Manual", "desfazer": "Desfazer"}


def _stamp(now=None):
    return (now or datetime.now()).strftime("%d-%m-%Y")


def report_filename(now=None, prefix="NeonCart_Relatorio"):
    return "{}_{}.xlsx".format(prefix, _stamp(now))


def history_filename(now=None):
    return report_filename(now, "NeonCart_Historico")


def backup_filename(now=None):
    now = now or datetime.now()
    return "NeonCart_Backup_{}.json".format(now.strftime("%d-%m-%Y_%H%M"))


def safe_name(text):
    keep = "".join(c if c.isalnum() or c in "-_" else "_" for c in text.strip())
    return keep.strip("_")[:40] or "Lista"


def _styles():
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    return {
        "head_fill": PatternFill("solid", fgColor="4C1D95"),
        "head_font": Font(name="Arial", bold=True, color="FFFFFF"),
        "head_border": Border(*(Side(style="thin", color="7E22CE"),) * 4),
        "cell_border": Border(*(Side(style="thin", color="E2E8F0"),) * 4),
        "zebra": PatternFill("solid", fgColor="F8FAFC"),
        "body_font": Font(name="Arial", color="334155"),
        "code_font": Font(name="Arial", bold=True, color="BE185D"),
        "left": Alignment(horizontal="left", vertical="center"),
    }


def _write_table(ws, headers, rows, widths, code_col=2, st=None):
    st = st or _styles()
    ws.append(headers)
    for cell in ws[1]:
        cell.fill = st["head_fill"]
        cell.font = st["head_font"]
        cell.border = st["head_border"]
        cell.alignment = st["left"]
    ws.row_dimensions[1].height = 24
    for idx, row in enumerate(rows, start=2):
        ws.append(row)
        for col, cell in enumerate(ws[idx], start=1):
            cell.border = st["cell_border"]
            cell.font = st["code_font"] if col == code_col else st["body_font"]
            # Mantém códigos numéricos como texto (sem notação científica).
            cell.number_format = "@"
            if idx % 2 == 1:
                cell.fill = st["zebra"]
    for i, width in enumerate(widths):
        ws.column_dimensions[chr(ord("A") + i)].width = width
    ws.freeze_panes = "A2"


def export_xlsx(entries, path, title="Carrinhos"):
    """Planilha com os registros e uma aba de resumo por setor."""
    from openpyxl import Workbook

    st = _styles()
    wb = Workbook()
    ws = wb.active
    ws.title = "Carrinhos"
    rows = [[local_datetime(e).strftime("%d/%m/%Y %H:%M:%S"), e["code"], e["division"],
             e.get("observation") or "-"] for e in entries]
    _write_table(ws, HEADERS, rows, (22, 26, 22, 40), st=st)

    summary = wb.create_sheet("Resumo")
    counts = Counter(e["division"] for e in entries)
    srows = [[div, n] for div, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]
    srows.append(["TOTAL", len(entries)])
    _write_table(summary, ["DIVISÓRIA / SETOR", "CARRINHOS"], srows, (28, 14), code_col=0, st=st)
    for cell in summary[summary.max_row]:
        cell.font = st["code_font"]
    for row in summary.iter_rows(min_row=2, min_col=2, max_col=2):
        row[0].number_format = "0"
    summary["D1"] = title
    summary["D1"].font = st["code_font"]
    wb.save(path)
    return path


def export_history_xlsx(history, path):
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Histórico"
    rows = [[local_datetime(h).strftime("%d/%m/%Y %H:%M:%S"),
             ACTION_LABELS.get(h["action"], h["action"]), h["code"], h["division"] or "-",
             SOURCE_LABELS.get(h.get("source"), h.get("source") or "-")] for h in history]
    _write_table(ws, HISTORY_HEADERS, rows, (22, 14, 26, 22, 12), code_col=3)
    wb.save(path)
    return path


MATERIAL_TITLE = "CONTROLE DE MATERIAL CIRCULANTE"
MATERIAL_HEADERS = ["Nº", "DATA DE DEVOLUÇÃO", "CLIENTE"]
MATERIAL_WIDTHS = {"A": 7, "B": 15, "C": 26}
STATUS_FILL = {"AGUARDANDO": ("B45309", "FEF3C7"), "DEVOLVIDO": ("15803D", "DCFCE7")}
_BAD_SHEET_CHARS = set("[]:*?/\\")


def _xl_styles():
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    thin = Side(style="thin", color="9FB3C8")
    return {
        "border": Border(left=thin, right=thin, top=thin, bottom=thin),
        "center": Alignment(horizontal="center", vertical="center"),
        "left": Alignment(horizontal="left", vertical="center", indent=1),
        "left_wrap": Alignment(horizontal="left", vertical="center", indent=1, wrap_text=True),
        "title_font_small": Font(name="Aptos Narrow", size=12, bold=True, color="FFFFFF"),
        "wrap": Alignment(horizontal="center", vertical="center", wrap_text=True),
        "title_font": Font(name="Aptos Narrow", size=18, bold=True, color="FFFFFF"),
        "title_fill": PatternFill("solid", fgColor="1F4E78"),
        "head_font": Font(name="Aptos Narrow", size=10, bold=True, color="FFFFFF"),
        "head_fill": PatternFill("solid", fgColor="2F75B5"),
        "info_font": Font(name="Aptos Narrow", size=11, bold=True, color="1E293B"),
        "info_fill": PatternFill("solid", fgColor="EAF1F8"),
        "body": Font(name="Aptos Narrow", size=11),
        "zebra": PatternFill("solid", fgColor="F6F9FC"),
        "total_font": Font(name="Aptos Narrow", size=11, bold=True, color="1F4E78"),
    }


def _status_style(cell, status):
    from openpyxl.styles import Font, PatternFill

    fg, bg = STATUS_FILL[status]
    cell.font = Font(name="Aptos Narrow", size=11, bold=True, color=fg)
    cell.fill = PatternFill("solid", fgColor=bg)


def _sheet_title(name, used):
    """Nome de aba válido (até 31 caracteres, sem caracteres proibidos) e único."""
    clean = "".join("-" if c in _BAD_SHEET_CHARS else c for c in name).strip()[:31] or "PASTA"
    title, n = clean, 2
    while title in used:
        suffix = " ({})".format(n)
        title = clean[:31 - len(suffix)] + suffix
        n += 1
    used.add(title)
    return title


PHOTO_COLS = (1, 5, 9, 13)   # colunas onde cada foto começa (A, E, I, M)
PHOTO_ROW_PT = 150           # altura (pontos) da linha de fotos


def _photos_section(ws, records, photos_dir, row, ncol, st):
    """Fotos abaixo da tabela: título por cliente e até 4 fotos por linha."""
    import io as _io

    from openpyxl.drawing.image import Image as XLImage
    from openpyxl.styles import Font

    import photos as ph
    import portavasos as pv

    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=ncol)
    title = ws.cell(row=row, column=1, value="FOTOS")
    title.font, title.fill, title.alignment = st["head_font"], st["head_fill"], st["left"]
    ws.row_dimensions[row].height = 22
    row += 1
    for n, r in enumerate(records, start=1):
        names = [p for p in r.get("photos", []) if ph.exists(photos_dir, p)]
        if not names:
            continue
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=ncol)
        head = ws.cell(row=row, column=1, value="{}. {}  ·  devolução {}  ·  {} foto(s)".format(
            n, r["client"], pv.format_date(r["date"]), len(names)))
        head.font = Font(name="Aptos Narrow", size=11, bold=True, color="1F4E78")
        head.fill, head.alignment = st["info_fill"], st["left"]
        ws.row_dimensions[row].height = 20
        row += 1
        for i in range(0, len(names), len(PHOTO_COLS)):
            ws.row_dimensions[row].height = PHOTO_ROW_PT
            for col, name in zip(PHOTO_COLS, names[i:i + len(PHOTO_COLS)]):
                data, _size = ph.thumbnail_for_excel(photos_dir, name)
                if data is None:
                    continue
                img = XLImage(_io.BytesIO(data))
                ws.add_image(img, "{}{}".format(_col_letter(col), row))
            row += 1
        row += 1  # espaço entre clientes
    return row


def _col_letter(col):
    from openpyxl.utils import get_column_letter

    return get_column_letter(col)


def _table_header(ws, row, headers, st):
    for col, text in enumerate(headers, start=1):
        c = ws.cell(row=row, column=col, value=text)
        c.fill, c.font, c.alignment, c.border = (
            st["head_fill"], st["head_font"], st["wrap"], st["border"])
    ws.row_dimensions[row].height = 36


def _section_title(ws, row, text, ncol, st):
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=ncol)
    c = ws.cell(row=row, column=1, value=text)
    c.font, c.fill, c.alignment = st["title_font_small"], st["title_fill"], st["left"]
    ws.row_dimensions[row].height = 24


def _record_row(ws, row, number, record, item_range, st, fill=None):
    """Uma devolução: Nº, data, cliente, materiais, total (fórmula) e códigos."""
    from datetime import date

    import portavasos as pv

    first_item, last_item = item_range
    values = [number, date.fromisoformat(record["date"]), record["client"]]
    values += [record["items"].get(name) for name in pv.ITEMS]
    values.append("=SUM({0}{2}:{1}{2})".format(first_item, last_item, row))
    values.append(pv.carts_text(record) or None)
    ncodes = len(values)
    for col, value in enumerate(values, start=1):
        c = ws.cell(row=row, column=col, value=value)
        c.font, c.border = st["body"], st["border"]
        c.alignment = st["left"] if col in (3, ncodes) else st["center"]
        if fill is not None:
            c.fill = fill
        if col == 2:
            c.number_format = "DD/MM/YYYY"
    if record.get("carts"):
        ws.cell(row=row, column=ncodes).alignment = st["left_wrap"]


def _sum_row(ws, row, label, first, last, ncol, st, items_cols):
    """Linha de total: rótulo + SOMA de cada coluna de material e do TOTAL."""
    from openpyxl.utils import get_column_letter

    ws.cell(row=row, column=3, value=label)
    for col in items_cols:
        letter = get_column_letter(col)
        ws.cell(row=row, column=col, value="=SUM({0}{1}:{0}{2})".format(letter, first, last))
    for col in range(1, ncol + 1):
        c = ws.cell(row=row, column=col)
        c.font, c.fill, c.border = st["total_font"], st["info_fill"], st["border"]
        c.alignment = st["left"] if col == 3 else st["center"]
    ws.row_dimensions[row].height = 22


def _folder_sheet(ws, folder, st, photos_dir=None):
    """Aba de uma pasta.

    1) DEVOLUÇÕES POR DIA: uma linha por devolução, em ordem de data, + total.
    2) RESUMO POR CLIENTE: cada devolução do cliente com a data e, quando ele
       devolveu mais de uma vez, a linha TOTAL do cliente.
    3) FOTOS (opcional).
    """
    from openpyxl.utils import get_column_letter

    import portavasos as pv

    headers = MATERIAL_HEADERS + pv.ITEMS + ["TOTAL", "CÓDIGOS DOS CARRINHOS"]
    ncol = len(headers)
    last = get_column_letter(ncol)
    n_fixed = len(MATERIAL_HEADERS)
    item_range = (get_column_letter(n_fixed + 1), get_column_letter(n_fixed + len(pv.ITEMS)))
    sum_cols = range(n_fixed + 1, n_fixed + len(pv.ITEMS) + 2)  # materiais + TOTAL

    ws.merge_cells("A1:{}1".format(last))
    ws["A1"] = MATERIAL_TITLE
    ws["A1"].font, ws["A1"].fill, ws["A1"].alignment = (
        st["title_font"], st["title_fill"], st["center"])
    ws.row_dimensions[1].height = 32

    status = folder["status"]
    status_text = pv.STATUS_LABELS[status]
    if status == pv.RETURNED and folder["status_date"]:
        status_text += " EM " + pv.format_date(folder["status_date"][:10])
    split = n_fixed + 8  # dados à esquerda, status à direita
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=split)
    ws.merge_cells(start_row=2, start_column=split + 1, end_row=2, end_column=ncol)
    info = ws.cell(row=2, column=1, value="PASTA: {}     PERÍODO: {}".format(
        folder["name"], pv.period_text(folder)))
    info.font, info.fill, info.alignment = st["info_font"], st["info_fill"], st["left"]
    cell = ws.cell(row=2, column=split + 1, value="STATUS: " + status_text)
    _status_style(cell, status)
    cell.alignment = st["center"]
    ws.row_dimensions[2].height = 24
    for col in range(1, ncol + 1):
        ws.cell(row=1, column=col).border = st["border"]
        ws.cell(row=2, column=col).border = st["border"]

    # 1) devoluções por dia
    _section_title(ws, 3, "DEVOLUÇÕES POR DIA", ncol, st)
    _table_header(ws, 4, headers, st)
    records = pv.sort_records(folder["records"])
    first_row = 5
    row = first_row
    for n, r in enumerate(records, start=1):
        _record_row(ws, row, n, r, item_range, st, st["zebra"] if n % 2 == 0 else None)
        row += 1
    if not records:
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=ncol)
        c = ws.cell(row=row, column=1, value="Nenhum cliente registrado nesta pasta.")
        c.alignment, c.font = st["center"], st["body"]
        row += 1
    else:
        _sum_row(ws, row, "TOTAL DA PASTA", first_row, row - 1, ncol, st, sum_cols)
        row += 1

    # 2) resumo por cliente
    if records:
        row += 1
        _section_title(ws, row, "RESUMO POR CLIENTE  ·  data de cada devolução e total",
                       ncol, st)
        row += 1
        _table_header(ws, row, ["DEV.", "DATA DE DEVOLUÇÃO", "CLIENTE"] + headers[n_fixed:], st)
        row += 1
        for i, (client, recs, _sums, _total) in enumerate(pv.client_summary(records)):
            fill = st["zebra"] if i % 2 else None
            start = row
            for k, r in enumerate(recs, start=1):
                _record_row(ws, row, "{}ª".format(k), r, item_range, st, fill)
                row += 1
            if len(recs) > 1:
                _sum_row(ws, row, "TOTAL {} ({} devoluções)".format(client, len(recs)),
                         start, row - 1, ncol, st, sum_cols)
                row += 1

    # 3) fotos
    if photos_dir and any(r.get("photos") for r in records):
        _photos_section(ws, records, photos_dir, row + 1, ncol, st)

    for col in range(1, ncol + 1):
        letter = get_column_letter(col)
        ws.column_dimensions[letter].width = MATERIAL_WIDTHS.get(letter, 10.5)
    ws.column_dimensions[last].width = 30
    ws.freeze_panes = "D5"
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_title_rows = "1:2"


def _summary_sheet(ws, folders, st):
    import portavasos as pv

    headers = ["Nº", "PASTA", "PERÍODO", "STATUS", "CLIENTES", "ITENS"]
    ws.merge_cells("A1:F1")
    ws["A1"] = MATERIAL_TITLE + " - PASTAS"
    ws["A1"].font, ws["A1"].fill, ws["A1"].alignment = (
        st["title_font"], st["title_fill"], st["center"])
    ws.row_dimensions[1].height = 32
    for col, text in enumerate(headers, start=1):
        c = ws.cell(row=2, column=col, value=text)
        c.fill, c.font, c.alignment, c.border = (
            st["head_fill"], st["head_font"], st["wrap"], st["border"])
    ws.row_dimensions[2].height = 24
    for n, f in enumerate(folders, start=1):
        row = n + 2
        values = [n, f["name"], pv.period_text(f), pv.STATUS_LABELS[f["status"]],
                  len(pv.totals_by_client(f["records"])), pv.folder_total(f)]
        for col, value in enumerate(values, start=1):
            c = ws.cell(row=row, column=col, value=value)
            c.font, c.border = st["body"], st["border"]
            c.alignment = st["left"] if col == 2 else st["center"]
        _status_style(ws.cell(row=row, column=4), f["status"])
    total_row = len(folders) + 3
    ws.cell(row=total_row, column=2, value="TOTAL")
    ws.cell(row=total_row, column=6, value="=SUM(F3:F{})".format(total_row - 1))
    for col in range(1, 7):
        c = ws.cell(row=total_row, column=col)
        c.font, c.fill, c.border = st["total_font"], st["info_fill"], st["border"]
        c.alignment = st["left"] if col == 2 else st["center"]
    for letter, width in zip("ABCDEF", (6, 28, 26, 26, 11, 11)):
        ws.column_dimensions[letter].width = width
    ws.freeze_panes = "A3"


def export_folders_xlsx(folders, path, photos_dir=None):
    """Uma aba por pasta; com mais de uma pasta, abre com a aba RESUMO.

    Com photos_dir, as fotos de cada cliente entram abaixo da tabela.
    """
    from openpyxl import Workbook

    st = _xl_styles()
    wb = Workbook()
    wb.remove(wb.active)
    used = set()
    if len(folders) != 1:
        _summary_sheet(wb.create_sheet(_sheet_title("RESUMO", used)), folders, st)
    for folder in folders:
        _folder_sheet(wb.create_sheet(_sheet_title(folder["name"], used)), folder, st,
                      photos_dir)
    wb.save(path)
    return path


def export_backup(data, path):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    return path


def share_text(entries, now=None, title=None):
    now = now or datetime.now()
    head = title or "Relatório de Carrinhos - {}".format(now.strftime("%d/%m/%Y"))
    lines = ["*{}*".format(head), ""]
    for e in entries:
        line = "🛒 *{}* (Div: {})".format(e["code"], e["division"])
        if e.get("observation"):
            line += " - _Obs: {}_".format(e["observation"])
        lines.append(line)
    lines.append("")
    lines.append("*Total:* {} carrinhos.".format(len(entries)))
    return "\n".join(lines)


def summary_text(summary, now=None):
    now = now or datetime.now()
    lines = ["*Resumo Neon Cart - {}*".format(now.strftime("%d/%m/%Y %H:%M")), ""]
    lines.append("*Na lista:* {} carrinhos".format(summary["total"]))
    for div, n in summary["divisions"]:
        lines.append("• {}: {}".format(div, n))
    lines.append("")
    lines.append("*Hoje:* {} registrados, {} duplicados, {} leituras".format(
        summary["today_added"], summary["today_duplicates"], summary["today_scans"]))
    return "\n".join(lines)
