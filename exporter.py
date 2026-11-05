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
