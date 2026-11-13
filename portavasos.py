"""Porta Vasos: devolução de material circulante em pastas semanais (sem Kivy).

Cada pasta é uma semana (ex.: "SEMANA 09.11 - 15.11") com um status
(AGUARDANDO DEVOLUÇÃO ou DEVOLVIDO). Dentro dela ficam os registros:
cliente, data de devolução e a quantidade de cada material.
"""

import uuid
from datetime import date, datetime, timedelta

# Materiais (mesma ordem das colunas da planilha).
ITEMS = [
    "CARRINHOS", "DIVISÓRIAS", "CESTO MOD 1", "CESTO MOD 2", "SUP MOD 2",
    "SUP LONGO MOD 2", "PTV P06", "PTV P09", "PTV P11", "PTV P13", "PTV P15",
    "PTV P17", "PTV C21", "CEST MULTI",
]

WAITING = "AGUARDANDO"
RETURNED = "DEVOLVIDO"
STATUSES = (WAITING, RETURNED)
STATUS_LABELS = {WAITING: "AGUARDANDO DEVOLUÇÃO", RETURNED: "DEVOLVIDO"}

MAX_QTY = 99999


class PvError(ValueError):
    """Dados inválidos (mensagem pronta para o usuário)."""


# Compatibilidade com o nome usado antes.
ReturnError = PvError


# --- datas ---------------------------------------------------------------
def parse_date(text, today=None):
    """Lê "DD/MM/AAAA", "DD/MM/AA", "DD/MM" (ano atual), "DDMMAAAA" ou ISO."""
    today = today or date.today()
    text = (text or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        pass
    for sep in "-.":
        text = text.replace(sep, "/")
    if "/" in text:
        parts = [p for p in text.split("/") if p]
    elif text.isdigit() and len(text) in (4, 6, 8):
        parts = [text[:2], text[2:4]] + ([text[4:]] if len(text) > 4 else [])
    else:
        return None
    if len(parts) not in (2, 3) or not all(p.isdigit() for p in parts):
        return None
    day, month = int(parts[0]), int(parts[1])
    year = today.year
    if len(parts) == 3:
        year = int(parts[2])
        if year < 100:
            year += 2000
    try:
        return date(year, month, day)
    except ValueError:
        return None


def format_date(value, short=False):
    """date/ISO -> "DD/MM/AAAA" (ou "DD/MM" se short). "" se inválida."""
    if isinstance(value, str):
        try:
            value = date.fromisoformat(value)
        except ValueError:
            return ""
    if not value:
        return ""
    return value.strftime("%d/%m" if short else "%d/%m/%Y")


def week_bounds(day):
    """Semana de domingo a sábado que contém o dia."""
    start = day - timedelta(days=(day.weekday() + 1) % 7)
    return start, start + timedelta(days=6)


def default_folder_name(start, end):
    return "SEMANA {} - {}".format(start.strftime("%d.%m"), end.strftime("%d.%m"))


def now_iso():
    return datetime.now().astimezone().isoformat()


# --- normalização --------------------------------------------------------
def normalize_text(value):
    return " ".join((value or "").split()).upper()


normalize_client = normalize_text


def clean_items(items):
    """Só materiais conhecidos com quantidade inteira > 0."""
    out = {}
    for name, qty in (items or {}).items():
        if name not in ITEMS:
            continue
        try:
            qty = int(qty)
        except (TypeError, ValueError):
            continue
        if qty > 0:
            out[name] = min(qty, MAX_QTY)
    return out


# --- registros -----------------------------------------------------------
def clean_photos(photos):
    out = []
    for name in photos or []:
        if isinstance(name, str) and name.strip() and name not in out:
            out.append(name.strip())
    return out


CART_ITEM = "CARRINHOS"


def normalize_cart_code(value):
    return "".join((value or "").split()).upper()


def clean_carts(codes):
    """Códigos dos carrinhos: maiúsculas, sem espaços, sem repetição."""
    out = []
    for code in codes or []:
        code = normalize_cart_code(code) if isinstance(code, str) else ""
        if code and code not in out:
            out.append(code)
    return out


def build_record(client, return_date, items, record_id=None, timestamp=None, photos=None,
                 carts=None):
    """Valida um cliente da pasta. Levanta PvError.

    carts: códigos dos carrinhos (bipados ou digitados). Quando informado, a
    quantidade de CARRINHOS é a quantidade de códigos. None mantém a quantidade
    de CARRINHOS que veio em items (registros antigos, sem códigos).
    """
    client = normalize_text(client)
    if not client:
        raise PvError("Informe o CLIENTE.")
    day = parse_date(return_date)
    if day is None:
        raise PvError("DATA DE DEVOLUÇÃO inválida. Use DD/MM/AAAA.")
    items = clean_items(items)
    codes = []
    if carts is not None:
        codes = clean_carts(carts)
        items.pop(CART_ITEM, None)
        if codes:
            items[CART_ITEM] = len(codes)
    if not items:
        raise PvError("Informe a quantidade de pelo menos um material "
                      "ou o código de um carrinho.")
    return {
        "id": record_id or str(uuid.uuid4()),
        "client": client,
        "date": day.isoformat(),
        "items": {name: items[name] for name in ITEMS if name in items},
        "carts": codes,
        "photos": clean_photos(photos),
        "timestamp": timestamp or now_iso(),
    }


def clean_record(r):
    if not isinstance(r, dict) or not isinstance(r.get("id"), str):
        return None
    try:
        return build_record(r.get("client"), r.get("date") or "", r.get("items"),
                            record_id=r["id"], timestamp=r.get("timestamp"),
                            photos=r.get("photos"), carts=r.get("carts") or None)
    except PvError:
        return None


def carts_text(record, sep=", "):
    return sep.join(record.get("carts", []))


def find_cart(folder, code, exclude_id=None):
    """Registro da pasta que já tem o carrinho (ou None)."""
    code = normalize_cart_code(code)
    for r in folder["records"]:
        if r["id"] != exclude_id and code in r.get("carts", []):
            return r
    return None


def record_total(record):
    return sum(record["items"].values())


def sort_records(records):
    return sorted(records, key=lambda r: (r["date"], r["timestamp"]))


def items_text(record, sep="  ·  ", with_codes=True):
    parts = []
    for name in ITEMS:
        if name not in record["items"]:
            continue
        text = "{}: {}".format(name, record["items"][name])
        if name == CART_ITEM and with_codes and record.get("carts"):
            text += " ({})".format(carts_text(record))
        parts.append(text)
    return sep.join(parts)


def client_summary(records):
    """Devoluções agrupadas por cliente (na ordem da 1ª devolução).

    Retorna [(cliente, [registros por data], somas_por_material, total)].
    """
    groups = {}
    for r in sort_records(records):
        groups.setdefault(r["client"], []).append(r)
    out = []
    for client, recs in groups.items():
        sums, total = totals(recs)
        out.append((client, recs, sums, total))
    return out


# --- pastas --------------------------------------------------------------
def build_folder(name, start, end, folder_id=None, created=None):
    """Valida os dados de uma pasta. Levanta PvError."""
    d_start = parse_date(start)
    if d_start is None:
        raise PvError("Data de INÍCIO inválida. Use DD/MM/AAAA.")
    d_end = parse_date(end) if (end or "").strip() else d_start + timedelta(days=6)
    if d_end is None:
        raise PvError("Data de FIM inválida. Use DD/MM/AAAA.")
    if d_end < d_start:
        raise PvError("A data de FIM é antes do INÍCIO.")
    name = normalize_text(name) or default_folder_name(d_start, d_end)
    return {
        "id": folder_id or str(uuid.uuid4()),
        "name": name,
        "start": d_start.isoformat(),
        "end": d_end.isoformat(),
        "status": WAITING,
        "status_date": "",
        "created": created or now_iso(),
        "records": [],
    }


def clean_folder(f):
    if not isinstance(f, dict) or not isinstance(f.get("id"), str):
        return None
    try:
        folder = build_folder(f.get("name"), f.get("start") or "", f.get("end") or "",
                              folder_id=f["id"], created=f.get("created"))
    except PvError:
        return None
    if f.get("status") in STATUSES:
        folder["status"] = f["status"]
    folder["status_date"] = f.get("status_date") or ""
    folder["records"] = [r for r in (clean_record(x) for x in f.get("records") or []) if r]
    return folder


def clean_folders(items):
    return sort_folders([f for f in (clean_folder(x) for x in items or []) if f])


def sort_folders(folders):
    """Semana mais recente primeiro."""
    return sorted(folders, key=lambda f: (f["start"], f["created"]), reverse=True)


def period_text(folder, short=False):
    return "{} a {}".format(format_date(folder["start"], short), format_date(folder["end"], short))


def totals(records):
    """Soma por material (na ordem da planilha) e total geral."""
    sums = {name: 0 for name in ITEMS}
    for r in records:
        for name, qty in r["items"].items():
            sums[name] += qty
    return sums, sum(sums.values())


def folder_total(folder):
    return sum(record_total(r) for r in folder["records"])


def totals_by_client(records):
    out = {}
    for r in records:
        out[r["client"]] = out.get(r["client"], 0) + record_total(r)
    return sorted(out.items(), key=lambda kv: (-kv[1], kv[0]))


def used_items(records):
    """Materiais que aparecem nos registros (na ordem da planilha)."""
    used = {name for r in records for name in r["items"]}
    return [name for name in ITEMS if name in used]


def all_records(folders):
    return [r for f in folders for r in f["records"]]


def all_photos(folders):
    return [name for f in folders for r in f["records"] for name in r.get("photos", [])]


# --- texto para compartilhar ---------------------------------------------
def record_text(record, folder=None):
    """Um cliente, pronto para colar no WhatsApp."""
    lines = ["*DEVOLUÇÃO DE MATERIAL — {}*".format(record["client"])]
    if folder is not None:
        lines.append("📁 {} ({})".format(folder["name"], STATUS_LABELS[folder["status"]]))
    lines.append("📅 Devolução: {}".format(format_date(record["date"])))
    lines.append("")
    for name in ITEMS:
        if name in record["items"]:
            line = "• {}: *{}*".format(name, record["items"][name])
            if name == CART_ITEM and record.get("carts"):
                line += " ({})".format(carts_text(record))
            lines.append(line)
    lines.append("")
    lines.append("*Total:* {} itens".format(record_total(record)))
    photos = len(record.get("photos", []))
    if photos:
        lines.append("📷 {} foto(s) registrada(s)".format(photos))
    return "\n".join(lines)


def folder_text(folder):
    lines = [
        "📁 *{}*".format(folder["name"]),
        "Período: {}".format(period_text(folder)),
        "Status: *{}*{}".format(
            STATUS_LABELS[folder["status"]],
            " em {}".format(format_date(folder["status_date"][:10]))
            if folder["status"] == RETURNED and folder["status_date"] else ""),
        "",
    ]
    records = sort_records(folder["records"])
    if not records:
        lines.append("_Pasta vazia._")
    for n, r in enumerate(records, start=1):
        lines.append("*{}. {}* — devolução {}".format(n, r["client"], format_date(r["date"])))
        photos = len(r.get("photos", []))
        lines.append("   " + items_text(r, ", ") + "  (*{}*)".format(record_total(r))
                     + ("  📷{}".format(photos) if photos else ""))
    sums, total = totals(records)
    if total:
        lines.append("")
        lines.append("*Totais da pasta:*")
        lines += ["• {}: {}".format(name, qty) for name, qty in sums.items() if qty]
        lines.append("*Total:* {} itens · {} clientes".format(
            total, len(totals_by_client(records))))
    return "\n".join(lines)


def share_text(folders, title="Material Circulante - Porta Vasos"):
    if len(folders) == 1:
        return folder_text(folders[0])
    parts = ["*{}*".format(title)]
    for folder in folders:
        parts.append(folder_text(folder))
    return "\n\n────────────\n\n".join(parts)
