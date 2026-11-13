import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import exporter  # noqa: E402
import pdfgen  # noqa: E402
import portavasos as pv  # noqa: E402
import reports  # noqa: E402
from storage import Database  # noqa: E402


@pytest.fixture
def db(tmp_path):
    return Database(str(tmp_path / "neoncart.json"))


def reload(db):
    return Database(db.path)


TODAY = date(2026, 11, 13)


@pytest.mark.parametrize("text,expected", [
    ("09/09/2026", date(2026, 9, 9)),
    ("9/9/26", date(2026, 9, 9)),
    ("15/09", date(2026, 9, 15)),
    ("15-09-2026", date(2026, 9, 15)),
    ("15092026", date(2026, 9, 15)),
    ("1509", date(2026, 9, 15)),
    ("2026-09-15", date(2026, 9, 15)),
    ("31/02/2026", None),
    ("abc", None),
    ("", None),
])
def test_parse_date(text, expected):
    assert pv.parse_date(text, today=TODAY) == expected


def test_week_bounds_and_default_name():
    start, end = pv.week_bounds(date(2026, 11, 13))  # sexta
    assert (start, end) == (date(2026, 11, 8), date(2026, 11, 14))
    assert pv.week_bounds(date(2026, 11, 8))[0] == date(2026, 11, 8)  # domingo
    assert pv.default_folder_name(start, end) == "SEMANA 08.11 - 14.11"


# --- pastas --------------------------------------------------------------
def test_add_folder_defaults_and_validation(db):
    f = db.add_folder("", "08/11/2026", "")
    assert f["name"] == "SEMANA 08.11 - 14.11"
    assert f["end"] == "2026-11-14"
    assert f["status"] == pv.WAITING
    with pytest.raises(pv.PvError, match="Já existe"):
        db.add_folder("outra", "08/11/2026", "")
    with pytest.raises(pv.PvError):
        db.add_folder("x", "99/99", "")
    with pytest.raises(pv.PvError):
        db.add_folder("x", "10/11/2026", "01/11/2026")
    assert len(reload(db).folders) == 1


def test_folders_sorted_newest_first(db):
    db.add_folder("", "01/11/2026", "")
    db.add_folder("", "15/11/2026", "")
    db.add_folder("", "08/11/2026", "")
    assert [f["start"] for f in db.folders] == ["2026-11-15", "2026-11-08", "2026-11-01"]
    assert [f["start"] for f in reload(db).folders] == ["2026-11-15", "2026-11-08", "2026-11-01"]


def test_folder_status_and_rename(db):
    f = db.add_folder("", "08/11/2026", "")
    db.set_folder_status(f["id"], pv.RETURNED)
    assert db.get_folder(f["id"])["status"] == pv.RETURNED
    assert db.get_folder(f["id"])["status_date"]
    assert db.folders_by_status(pv.WAITING) == []
    db.set_folder_status(f["id"], pv.WAITING)
    assert db.get_folder(f["id"])["status_date"] == ""
    db.update_folder(f["id"], "semana especial", "09/11/2026", "13/11/2026")
    again = reload(db).get_folder(f["id"])
    assert (again["name"], again["start"], again["end"]) == (
        "SEMANA ESPECIAL", "2026-11-09", "2026-11-13")


def test_records_in_folder(db):
    f = db.add_folder("", "08/11/2026", "")
    r = db.add_record(f["id"], " luiz  bh ", "09/11/2026",
                      {"PTV P11": "14", "PTV P15": 8, "CEST MULTI": 0, "XYZ": 3})
    assert r["client"] == "LUIZ BH"
    assert r["items"] == {"PTV P11": 14, "PTV P15": 8}
    assert db.clients == ["LUIZ BH"]
    with pytest.raises(pv.PvError):
        db.add_record(f["id"], "ALEF", "09/11/2026", {})
    with pytest.raises(pv.PvError):
        db.add_record(f["id"], "", "09/11/2026", {"PTV P11": 1})

    db.update_record(r["id"], "ALEF", "10/11/2026", {"CESTO MOD 1": 2})
    folder, rec = reload(db).find_record(r["id"])
    assert folder["id"] == f["id"] and rec["client"] == "ALEF" and rec["date"] == "2026-11-10"

    folder, rec, idx = db.remove_record(r["id"])
    assert db.get_folder(f["id"])["records"] == []
    assert db.restore_record(f["id"], rec, idx)
    assert reload(db).get_folder(f["id"])["records"][0]["client"] == "ALEF"


def test_delete_and_reinsert_folder(db):
    f = db.add_folder("", "08/11/2026", "")
    db.add_record(f["id"], "A", "09/11/2026", {"CARRINHOS": 1})
    removed = db.delete_folder(f["id"])
    assert db.folders == []
    db.reinsert_folder(removed)
    assert reload(db).folders[0]["records"][0]["client"] == "A"


def test_backup_keeps_folders(db, tmp_path):
    f = db.add_folder("", "08/11/2026", "")
    db.add_record(f["id"], "AURORA", "09/11/2026", {"CESTO MOD 1": 10})
    other = Database(str(tmp_path / "outro.json"))
    other.load_backup(db.backup_dict())
    assert other.folders == db.folders


def _sample_folders():
    f1 = pv.build_folder("", "08/11/2026", "")
    f1["records"] = [
        pv.build_record("LUIZ BH", "09/11/2026", {"PTV P11": 14, "PTV P15": 8}),
        pv.build_record("AURORA", "10/11/2026", {"CARRINHOS": 2, "CESTO MOD 1": 10}),
        pv.build_record("LUIZ BH", "11/11/2026", {"PTV P09": 5}),
    ]
    f2 = pv.build_folder("", "01/11/2026", "")
    f2["status"], f2["status_date"] = pv.RETURNED, "2026-11-08T10:00:00-03:00"
    f2["records"] = [pv.build_record("ERNANE", "03/11/2026", {"CESTO MOD 1": 4})]
    return f1, f2


def test_totals_and_text():
    f1, f2 = _sample_folders()
    sums, total = pv.totals(f1["records"])
    assert total == 39 and sums["PTV P11"] == 14
    assert pv.totals_by_client(f1["records"])[0] == ("LUIZ BH", 27)
    assert pv.used_items(f1["records"]) == ["CARRINHOS", "CESTO MOD 1", "PTV P09", "PTV P11",
                                            "PTV P15"]
    text = pv.folder_text(f2)
    assert "SEMANA 01.11 - 07.11" in text and "*DEVOLVIDO* em 08/11/2026" in text
    both = pv.share_text([f1, f2])
    assert "AGUARDANDO DEVOLUÇÃO" in both and "ERNANE" in both


# --- exportações ---------------------------------------------------------
def test_export_folders_xlsx(tmp_path):
    from openpyxl import load_workbook

    f1, f2 = _sample_folders()
    path = exporter.export_folders_xlsx([f1, f2], str(tmp_path / "pastas.xlsx"))
    wb = load_workbook(path)
    assert wb.sheetnames == ["RESUMO", "SEMANA 08.11 - 14.11", "SEMANA 01.11 - 07.11"]
    ws = wb["SEMANA 08.11 - 14.11"]
    assert ws["A1"].value == "CONTROLE DE MATERIAL CIRCULANTE"
    assert "AGUARDANDO DEVOLUÇÃO" in ws["L2"].value
    assert ws["A3"].value == "DEVOLUÇÕES POR DIA"
    assert [c.value for c in ws[4]][:4] == ["Nº", "DATA DE DEVOLUÇÃO", "CLIENTE", "CARRINHOS"]
    assert ws["S4"].value == "CÓDIGOS DOS CARRINHOS"
    assert ws["C5"].value == "LUIZ BH" and ws["B5"].value.date() == date(2026, 11, 9)
    assert ws["L5"].value == 14  # PTV P11
    assert ws["R5"].value == "=SUM(D5:Q5)"
    assert ws["C8"].value == "TOTAL DA PASTA" and ws["R8"].value == "=SUM(R5:R7)"
    assert wb["RESUMO"]["D4"].value == "DEVOLVIDO"
    # resumo por cliente: LUIZ BH devolveu 2 vezes -> 2 linhas com data + TOTAL
    col_c = [c.value for c in ws["C"]]
    i = col_c.index("TOTAL LUIZ BH (2 devoluções)")
    assert col_c[i - 2] == col_c[i - 1] == "LUIZ BH"
    assert [ws.cell(row=i - 1, column=1).value, ws.cell(row=i, column=1).value] == ["1ª", "2ª"]
    assert ws.cell(row=i + 1, column=18).value == "=SUM(R{}:R{})".format(i - 1, i)
    assert "TOTAL AURORA (1 devoluções)" not in col_c  # 1 devolução: sem linha extra

    single = load_workbook(exporter.export_folders_xlsx([f2], str(tmp_path / "uma.xlsx")))
    assert single.sheetnames == ["SEMANA 01.11 - 07.11"]


def test_sheet_titles_are_valid_and_unique():
    used = set()
    assert exporter._sheet_title("A/B:C", used) == "A-B-C"
    assert exporter._sheet_title("A/B:C", used) == "A-B-C (2)"
    assert len(exporter._sheet_title("X" * 40, used)) == 31


def test_export_pdf(tmp_path):
    f1, f2 = _sample_folders()
    f1["records"] *= 20  # força mais de uma página
    one = reports.export_folders_pdf([f2], str(tmp_path / "uma.pdf"))
    many = reports.export_folders_pdf([f1, f2], str(tmp_path / "todas.pdf"))
    for path in (one, many):
        data = open(path, "rb").read()
        assert data.startswith(b"%PDF-1.4") and data.rstrip().endswith(b"%%EOF")
    assert open(many, "rb").read().count(b"/Type /Page ") >= 4


# --- fotos ---------------------------------------------------------------
def _jpeg_bytes(size=(800, 600), color=(200, 30, 90)):
    import io

    from PIL import Image

    out = io.BytesIO()
    Image.new("RGB", size, color).save(out, "JPEG")
    return out.getvalue()


def test_photos_save_rotate_delete(tmp_path):
    import photos as ph
    from PIL import Image

    folder = str(tmp_path / "photos")
    name = ph.save_bytes(_jpeg_bytes((3000, 1000)), folder)
    with Image.open(ph.photo_path(folder, name)) as img:
        assert max(img.size) == ph.MAX_SIDE
    assert os.path.exists(ph.thumb_path(folder, name))
    assert ph.rotate(folder, name)
    with Image.open(ph.photo_path(folder, name)) as img:
        assert img.size[1] > img.size[0]
    ph.delete(folder, name)
    assert not ph.exists(folder, name)
    assert not os.path.exists(ph.thumb_path(folder, name))


def test_nv21_and_orientation():
    import photos as ph

    w, h = 8, 4
    buf = bytes([128] * (w * h)) + bytes([128] * (w * h // 2))
    img = ph.nv21_to_image(buf, w, h)
    assert img.size == (8, 4) and img.mode == "RGB"
    assert ph.orient(img, -90).size == (4, 8)
    assert ph.orient(img, 0, mirror=True).size == (8, 4)


def test_record_photos_and_purge(db):
    import photos as ph

    f = db.add_folder("", "08/11/2026", "")
    keep = ph.save_bytes(_jpeg_bytes(), db.photos_dir)
    orphan = ph.save_bytes(_jpeg_bytes(), db.photos_dir)
    r = db.add_record(f["id"], "ALEF", "09/11/2026", {"CARRINHOS": 1}, photos=[keep, keep])
    assert r["photos"] == [keep]
    # editar sem informar fotos mantém as fotos
    db.update_record(r["id"], "ALEF", "09/11/2026", {"CARRINHOS": 2})
    assert reload(db).find_record(r["id"])[1]["photos"] == [keep]
    assert db.purge_photos() == 1
    assert ph.exists(db.photos_dir, keep) and not ph.exists(db.photos_dir, orphan)
    db.set_record_photos(r["id"], [])
    assert reload(db).find_record(r["id"])[1]["photos"] == []


def test_purge_skipped_when_data_file_is_unreadable(tmp_path):
    import photos as ph

    path = tmp_path / "neoncart.json"
    path.write_bytes(b"\xff\xfe nao e json")
    db = Database(str(path))
    assert db.loaded_ok is False
    ph.save_bytes(_jpeg_bytes(), db.photos_dir)
    assert db.purge_photos() == 0


def test_export_xlsx_with_photos(tmp_path):
    import photos as ph
    from openpyxl import load_workbook

    photos_dir = str(tmp_path / "photos")
    f1, _f2 = _sample_folders()
    f1["records"][0]["photos"] = [ph.save_bytes(_jpeg_bytes(), photos_dir) for _ in range(5)]
    f1["records"][1]["photos"] = ["nao_existe.jpg"]
    with_photos = exporter.export_folders_xlsx([f1], str(tmp_path / "com.xlsx"), photos_dir)
    without = exporter.export_folders_xlsx([f1], str(tmp_path / "sem.xlsx"))
    ws = load_workbook(with_photos)["SEMANA 08.11 - 14.11"]
    assert len(ws._images) == 5
    titles = [c.value for c in ws["A"] if isinstance(c.value, str)]
    assert "FOTOS" in titles
    assert any(t.startswith("1. LUIZ BH") and "5 foto(s)" in t for t in titles)
    assert not any(t.startswith("2. AURORA") for t in titles)  # foto inexistente é ignorada
    assert len(load_workbook(without)["SEMANA 08.11 - 14.11"]._images) == 0
    assert os.path.getsize(with_photos) > os.path.getsize(without)


def test_record_text():
    f1, _ = _sample_folders()
    r = f1["records"][0]
    r["photos"] = ["a.jpg", "b.jpg"]
    text = pv.record_text(r, f1)
    assert text.startswith("*DEVOLUÇÃO DE MATERIAL — LUIZ BH*")
    assert "SEMANA 08.11 - 14.11 (AGUARDANDO DEVOLUÇÃO)" in text
    assert "• PTV P11: *14*" in text and "*Total:* 22 itens" in text
    assert "📷 2 foto(s)" in text


# --- carrinhos por código -------------------------------------------------
def test_cart_codes_set_quantity():
    r = pv.build_record("ALEF", "09/11/2026", {"CARRINHOS": 9, "PTV P11": 2},
                        carts=[" cr-01", "CR-02", "cr-01", ""])
    assert r["carts"] == ["CR-01", "CR-02"]
    assert r["items"]["CARRINHOS"] == 2  # vem dos códigos, não do número digitado
    assert "CARRINHOS: 2 (CR-01, CR-02)" in pv.items_text(r)
    assert "• CARRINHOS: *2* (CR-01, CR-02)" in pv.record_text(r)
    only_carts = pv.build_record("ALEF", "09/11/2026", {}, carts=["X1"])
    assert only_carts["items"] == {"CARRINHOS": 1}
    with pytest.raises(pv.PvError):
        pv.build_record("ALEF", "09/11/2026", {"CARRINHOS": 3}, carts=[])
    legacy = pv.clean_record({"id": "x", "client": "A", "date": "2026-11-09",
                              "items": {"CARRINHOS": 3}})
    assert legacy["items"]["CARRINHOS"] == 3 and legacy["carts"] == []


def test_cart_code_unique_in_folder(db):
    f = db.add_folder("", "08/11/2026", "")
    a = db.add_record(f["id"], "AURORA", "12/11/2026", {}, carts=["C1", "C2"])
    with pytest.raises(pv.PvError, match="C2 já foi registrado nesta pasta para AURORA"):
        db.add_record(f["id"], "LUIZ", "13/11/2026", {}, carts=["C2"])
    # editar o próprio registro mantendo os códigos é permitido
    db.update_record(a["id"], "AURORA", "12/11/2026", {"PTV P11": 1}, carts=["C1", "C2"])
    # editar sem informar carts mantém os códigos
    db.update_record(a["id"], "AURORA", "12/11/2026", {"PTV P11": 4})
    assert reload(db).find_record(a["id"])[1]["carts"] == ["C1", "C2"]
    other = db.add_folder("", "15/11/2026", "")
    assert db.add_record(other["id"], "LUIZ", "16/11/2026", {}, carts=["C2"])  # outra pasta


def test_same_client_several_returns(db):
    f = db.add_folder("", "08/11/2026", "")
    db.add_record(f["id"], "AURORA", "12/11/2026", {"PTV P11": 12})
    db.add_record(f["id"], "LUIZ", "12/11/2026", {"PTV P15": 3})
    db.add_record(f["id"], "aurora", "13/11/2026", {"PTV P13": 14})
    returns = db.client_returns(f["id"], "Aurora")
    assert [r["date"] for r in returns] == ["2026-11-12", "2026-11-13"]
    summary = pv.client_summary(db.get_folder(f["id"])["records"])
    assert [(c, len(rs), t) for c, rs, _s, t in summary] == [("AURORA", 2, 26), ("LUIZ", 1, 3)]


def test_client_list(db):
    f = db.add_folder("", "08/11/2026", "")
    db.add_record(f["id"], "ernane", "12/11/2026", {"PTV P11": 1})
    assert db.add_client("  aurora  bh ") == "AURORA BH"
    assert db.add_client("") is None
    assert db.client_list == ["AURORA BH", "ERNANE"]
    assert db.search_clients("aur") == ["AURORA BH"]
    assert reload(db).client_list == ["AURORA BH", "ERNANE"]
    assert db.remove_client("ernane")
    assert "ERNANE" not in reload(db).client_list
    assert db.get_folder(f["id"])["records"][0]["client"] == "ERNANE"  # registro continua


def test_pdf_with_codes_and_repeat_clients(tmp_path):
    f = pv.build_folder("", "08/11/2026", "")
    f["records"] = [
        pv.build_record("AURORA", "12/11/2026", {"PTV P11": 12}, carts=["CR-1"]),
        pv.build_record("AURORA", "13/11/2026", {"PTV P13": 14}),
    ]
    path = reports.export_folders_pdf([f], str(tmp_path / "x.pdf"))
    assert open(path, "rb").read().startswith(b"%PDF")


def test_pdf_text_helpers():
    assert pdfgen.text_width("AB", 10) == pytest.approx(13.34)
    assert pdfgen.wrap("SUP LONGO MOD 2", 7, 30, True) == ["SUP", "LONGO", "MOD 2"]
    assert pdfgen.fit("CLIENTE MUITO LONGO", 9, 40).endswith("...")
