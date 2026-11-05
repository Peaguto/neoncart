"""Relatório em Excel (.xlsx) e texto para compartilhar."""

from datetime import datetime

from storage import local_datetime

HEADERS = ["DATA / HORA", "CÓDIGO DO CARRINHO", "DIVISÓRIA / SETOR", "OBSERVAÇÕES"]


def report_filename(now=None):
    now = now or datetime.now()
    return "NeonCart_Relatorio_{}.xlsx".format(now.strftime("%d-%m-%Y"))


def export_xlsx(entries, path):
    """Gera a planilha com cabeçalho roxo e código em rosa, como no app web."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    wb = Workbook()
    ws = wb.active
    ws.title = "Carrinhos"

    head_fill = PatternFill("solid", fgColor="4C1D95")
    head_font = Font(name="Arial", bold=True, color="FFFFFF")
    head_border = Border(*(Side(style="thin", color="7E22CE"),) * 4)
    cell_border = Border(*(Side(style="thin", color="E2E8F0"),) * 4)
    zebra = PatternFill("solid", fgColor="F8FAFC")
    body_font = Font(name="Arial", color="334155")
    code_font = Font(name="Arial", bold=True, color="BE185D")

    ws.append(HEADERS)
    for cell in ws[1]:
        cell.fill = head_fill
        cell.font = head_font
        cell.border = head_border
        cell.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 24

    for idx, e in enumerate(entries, start=2):
        dt = local_datetime(e)
        ws.append([
            dt.strftime("%d/%m/%Y %H:%M:%S"),
            e["code"],
            e["division"],
            e.get("observation") or "-",
        ])
        for col, cell in enumerate(ws[idx], start=1):
            cell.border = cell_border
            cell.font = code_font if col == 2 else body_font
            # Mantém códigos numéricos como texto (sem notação científica).
            cell.number_format = "@"
            if idx % 2 == 1:
                cell.fill = zebra

    for col, width in zip("ABCD", (22, 26, 22, 40)):
        ws.column_dimensions[col].width = width
    ws.freeze_panes = "A2"
    wb.save(path)
    return path


def share_text(entries, now=None):
    now = now or datetime.now()
    lines = ["*Relatório de Carrinhos - {}*".format(now.strftime("%d/%m/%Y")), ""]
    for e in entries:
        line = "🛒 *{}* (Div: {})".format(e["code"], e["division"])
        if e.get("observation"):
            line += " - _Obs: {}_".format(e["observation"])
        lines.append(line)
    lines.append("")
    lines.append("*Total:* {} carrinhos.".format(len(entries)))
    return "\n".join(lines)
