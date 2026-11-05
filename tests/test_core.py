import os
import sys
from datetime import datetime

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from exporter import export_xlsx, report_filename, share_text  # noqa: E402
from storage import DuplicateCodeError, EntryStore  # noqa: E402


@pytest.fixture
def store(tmp_path):
    return EntryStore(str(tmp_path / "entries.json"))


def test_add_normalizes_and_persists(store):
    e = store.add("  abc123 ", " setor-x ", "  roda quebrada ")
    assert (e["code"], e["division"], e["observation"]) == ("ABC123", "SETOR-X", "roda quebrada")
    reloaded = EntryStore(store.path)
    assert reloaded.entries == store.entries


def test_newest_first(store):
    store.add("A1", "D")
    store.add("A2", "D")
    assert [e["code"] for e in store.entries] == ["A2", "A1"]


def test_requires_code_and_division(store):
    assert store.add("", "D") is None
    assert store.add("A1", "  ") is None
    assert store.entries == []


def test_duplicate_rejected_case_insensitive(store):
    store.add("abc", "D")
    with pytest.raises(DuplicateCodeError) as exc:
        store.add(" ABC ", "OUTRO")
    assert exc.value.code == "ABC"
    assert len(store.entries) == 1


def test_update_and_duplicate_on_edit(store):
    a = store.add("A1", "D1")
    store.add("B1", "D2")
    with pytest.raises(DuplicateCodeError):
        store.update(a["id"], "b1", "D1")
    updated = store.update(a["id"], "a1", "novo", " obs ")
    assert (updated["code"], updated["division"], updated["observation"]) == ("A1", "NOVO", "obs")


def test_remove_and_clear(store):
    a = store.add("A1", "D")
    store.add("B1", "D")
    store.remove(a["id"])
    assert [e["code"] for e in store.entries] == ["B1"]
    store.clear()
    assert EntryStore(store.path).entries == []


def test_filter(store):
    store.add("CART01", "SETOR-A", "Roda quebrada")
    store.add("CART02", "SETOR-B")
    assert [e["code"] for e in store.filter("cart01")] == ["CART01"]
    assert [e["code"] for e in store.filter("setor-b")] == ["CART02"]
    assert [e["code"] for e in store.filter("RODA")] == ["CART01"]
    assert len(store.filter("")) == 2


def test_corrupt_file_starts_empty(tmp_path):
    p = tmp_path / "entries.json"
    p.write_text("{nao é json")
    assert EntryStore(str(p)).entries == []


def test_share_text(store):
    store.add("A1", "D1", "obs")
    store.add("B2", "D2")
    text = share_text(store.entries, now=datetime(2026, 11, 5))
    assert text.splitlines()[0] == "*Relatório de Carrinhos - 05/11/2026*"
    assert "🛒 *B2* (Div: D2)" in text
    assert "🛒 *A1* (Div: D1) - _Obs: obs_" in text
    assert text.endswith("*Total:* 2 carrinhos.")


def test_export_xlsx(store, tmp_path):
    from openpyxl import load_workbook

    store.add("00123", "D1", "obs")
    store.add("B2", "D2")
    path = export_xlsx(store.entries, str(tmp_path / "r.xlsx"))
    ws = load_workbook(path).active
    rows = list(ws.values)
    assert rows[0] == ("DATA / HORA", "CÓDIGO DO CARRINHO", "DIVISÓRIA / SETOR", "OBSERVAÇÕES")
    assert rows[1][1:] == ("B2", "D2", "-")
    assert rows[2][1:] == ("00123", "D1", "obs")
    assert ws["A1"].fill.fgColor.rgb.endswith("4C1D95")


def test_report_filename():
    assert report_filename(datetime(2026, 11, 5)) == "NeonCart_Relatorio_05-11-2026.xlsx"


def test_scanner_decodes_code128():
    barcode = pytest.importorskip("barcode")
    from barcode.writer import ImageWriter

    from scanner import decode_gray

    img = barcode.get("code128", "CART-0042", writer=ImageWriter()).render()
    assert decode_gray(img.convert("L")) == "CART-0042"


def test_scanner_decodes_rotated_frame():
    """No Android o quadro vem deitado (sensor em paisagem)."""
    barcode = pytest.importorskip("barcode")
    from barcode.writer import ImageWriter

    from scanner import decode_gray

    img = barcode.get("code128", "CART-0042", writer=ImageWriter()).render()
    assert decode_gray(img.convert("L").rotate(90, expand=True)) == "CART-0042"
