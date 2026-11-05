import json
import os
import sys
from datetime import datetime

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import storage  # noqa: E402
from storage import (ADD, DELETE, DUPLICATE, EDIT, SCAN, BackupError, Database,  # noqa: E402
                     DuplicateCodeError)


@pytest.fixture
def db(tmp_path):
    return Database(str(tmp_path / "neoncart.json"))


def reload(db):
    return Database(db.path)


# --- histórico -----------------------------------------------------------
def test_history_logs_actions(db):
    db.log_scan("abc")
    a = db.add("abc", "d1", source="camera")
    with pytest.raises(DuplicateCodeError):
        db.add("ABC", "d1")
    db.update(a["id"], "abc", "d2")
    db.remove(a["id"])
    assert [h["action"] for h in db.history] == [DELETE, EDIT, DUPLICATE, ADD, SCAN]
    assert db.history[3]["source"] == "camera"
    assert reload(db).history == db.history


def test_history_filter_and_clear(db):
    db.add("A1", "SETOR-A")
    db.add("B1", "SETOR-B")
    with pytest.raises(DuplicateCodeError):
        db.add("A1", "SETOR-A")
    assert [h["code"] for h in db.filter_history(action=DUPLICATE)] == ["A1"]
    assert [h["code"] for h in db.filter_history("setor-b")] == ["B1"]
    db.clear_history()
    assert reload(db).history == []


def test_history_is_capped(db, monkeypatch):
    monkeypatch.setattr(Database, "MAX_HISTORY", 3)
    for i in range(5):
        db.log_scan("C{}".format(i))
    assert [h["code"] for h in db.history] == ["C4", "C3", "C2"]


# --- desfazer ------------------------------------------------------------
def test_remove_and_restore_position(db):
    db.add("A", "D")
    b = db.add("B", "D")
    db.add("C", "D")
    entry, idx = db.remove(b["id"])
    assert idx == 1
    assert db.restore(entry, idx)
    assert [e["code"] for e in db.entries] == ["C", "B", "A"]


def test_restore_fails_if_code_reused(db):
    a = db.add("A", "D")
    entry, idx = db.remove(a["id"])
    db.add("A", "D")
    assert db.restore(entry, idx) is False


def test_clear_and_restore_all(db):
    db.add("A", "D")
    removed = db.clear()
    assert db.entries == []
    assert db.restore_all(removed)
    assert [e["code"] for e in reload(db).entries] == ["A"]


# --- setores recentes ----------------------------------------------------
def test_recent_divisions(db, monkeypatch):
    monkeypatch.setattr(Database, "MAX_DIVISIONS", 2)
    db.add("A", "s1")
    db.add("B", "s2")
    db.add("C", "s1")
    assert db.divisions == ["S1", "S2"]
    db.add("D", "s3")
    assert db.divisions == ["S3", "S1"]
    db.forget_division("s1")
    assert reload(db).divisions == ["S3"]


# --- listas salvas -------------------------------------------------------
def test_save_session_moves_entries(db):
    assert db.save_session("x") is None  # lista vazia
    db.add("A", "D")
    db.add("B", "D")
    s = db.save_session("  Turno manhã ")
    assert s["name"] == "Turno manhã"
    assert [e["code"] for e in s["entries"]] == ["B", "A"]
    assert db.entries == []
    # código pode ser usado de novo na lista nova
    db.add("A", "D")
    assert [(where, e["code"]) for where, e in db.find_code("a")] == [
        ("Lista atual", "A"), ("Turno manhã", "A")]


def test_default_session_name(db):
    db.add("A", "D")
    s = db.save_session()
    assert s["name"].startswith("Lista ")
    assert Database.default_session_name(datetime(2026, 11, 5, 8, 30)) == "Lista 05/11/2026 08:30"


def test_rename_delete_reinsert_session(db):
    db.add("A", "D")
    s = db.save_session("x")
    assert db.rename_session(s["id"], " ") is None
    db.rename_session(s["id"], "novo")
    assert reload(db).sessions[0]["name"] == "novo"
    removed = db.delete_session(s["id"])
    assert db.sessions == []
    db.reinsert_session(removed)
    assert reload(db).sessions[0]["id"] == s["id"]


def test_restore_session_autosaves_active(db):
    db.add("A", "D1")
    s = db.save_session("antiga")
    db.add("B", "D2")
    restored, autosaved = db.restore_session(s["id"])
    assert restored["name"] == "antiga"
    assert [e["code"] for e in db.entries] == ["A"]
    assert autosaved["name"].endswith("(auto)")
    assert [e["code"] for e in autosaved["entries"]] == ["B"]
    assert [x["id"] for x in db.sessions] == [autosaved["id"]]


def test_restore_session_without_active(db):
    db.add("A", "D1")
    s = db.save_session("antiga")
    restored, autosaved = db.restore_session(s["id"])
    assert autosaved is None and db.sessions == []


# --- resumo / ajustes / backup ------------------------------------------
def test_summary(db):
    db.add("A", "S1", "obs")
    db.add("B", "S1")
    db.add("C", "S2")
    db.log_scan("A")
    with pytest.raises(DuplicateCodeError):
        db.add("A", "S1")
    s = db.summary()
    assert s["total"] == 3 and s["with_obs"] == 1
    assert s["divisions"] == [("S1", 2), ("S2", 1)]
    assert (s["today_added"], s["today_duplicates"], s["today_scans"]) == (3, 1, 1)


def test_settings_persist(db):
    assert db.settings["continuous"] is False
    db.set_setting("continuous", True)
    assert reload(db).settings["continuous"] is True
    with pytest.raises(KeyError):
        db.set_setting("nao_existe", True)


def test_backup_roundtrip(db, tmp_path):
    db.add("A", "D")
    db.save_session("salva")
    db.add("B", "D")
    text = json.dumps(db.backup_dict())
    other = Database(str(tmp_path / "other.json"))
    other.load_backup(text)
    assert [e["code"] for e in other.entries] == ["B"]
    assert other.sessions[0]["name"] == "salva"
    assert len(other.history) == len(db.history)


def test_backup_accepts_legacy_list(db):
    db.load_backup('[{"id": "1", "code": "x1", "division": "d", "timestamp": "2026-01-01T10:00:00Z"}]')
    assert db.entries[0]["code"] == "X1"


@pytest.mark.parametrize("bad", ["{nao json", '{"foo": 1}', "42"])
def test_backup_rejects_invalid(db, bad):
    db.add("A", "D")
    with pytest.raises(BackupError):
        db.load_backup(bad)
    assert [e["code"] for e in db.entries] == ["A"]


def test_migrates_v1_entries_file(tmp_path):
    legacy = tmp_path / "entries.json"
    legacy.write_text(json.dumps([{"id": "1", "code": "A", "division": "D",
                                   "observation": "", "timestamp": "2026-01-01T10:00:00+00:00"}]))
    db = Database(str(tmp_path / "neoncart.json"), legacy_path=str(legacy))
    assert [e["code"] for e in db.entries] == ["A"]
    assert os.path.exists(db.path)


def test_ignores_garbage_items(tmp_path):
    p = tmp_path / "neoncart.json"
    p.write_text(json.dumps({"entries": [1, {"id": "x"}, {"id": "y", "code": "ok", "division": "d"}],
                             "history": [{"action": "???", "code": "a"}],
                             "settings": {"vibrate": "sim"}}))
    db = Database(str(p))
    assert [e["code"] for e in db.entries] == ["OK"]
    assert db.history == []
    assert db.settings == storage.DEFAULT_SETTINGS


# --- exportação ----------------------------------------------------------
def test_export_has_summary_sheet(db, tmp_path):
    from openpyxl import load_workbook

    import exporter

    db.add("A", "S1")
    db.add("B", "S1")
    db.add("C", "S2")
    wb = load_workbook(exporter.export_xlsx(db.entries, str(tmp_path / "r.xlsx"), "Turno"))
    assert wb.sheetnames == ["Carrinhos", "Resumo"]
    rows = list(wb["Resumo"].iter_rows(min_row=2, max_col=2, values_only=True))
    assert rows == [("S1", 2), ("S2", 1), ("TOTAL", 3)]


def test_export_history(db, tmp_path):
    from openpyxl import load_workbook

    import exporter

    db.log_scan("A")
    db.add("A", "S1", source="camera")
    ws = load_workbook(exporter.export_history_xlsx(db.history, str(tmp_path / "h.xlsx"))).active
    rows = list(ws.iter_rows(min_row=2, min_col=2, values_only=True))
    assert rows == [("REGISTRADO", "A", "S1", "Câmera"), ("LIDO", "A", "-", "Câmera")]


def test_backup_file_roundtrip(db, tmp_path):
    import exporter

    db.add("A", "S1")
    path = exporter.export_backup(db.backup_dict(), str(tmp_path / "b.json"))
    other = Database(str(tmp_path / "o.json"))
    with open(path, encoding="utf-8") as fh:
        other.load_backup(fh.read())
    assert other.entries == db.entries


def test_texts_and_names():
    import exporter

    now = datetime(2026, 11, 5, 14, 7)
    assert exporter.backup_filename(now) == "NeonCart_Backup_05-11-2026_1407.json"
    assert exporter.history_filename(now) == "NeonCart_Historico_05-11-2026.xlsx"
    assert exporter.safe_name(" Turno/manhã 1 ") == "Turno_manhã_1"
    text = exporter.share_text([], now, title="Turno")
    assert text.startswith("*Turno*")
    s = {"total": 2, "divisions": [("S1", 2)], "today_added": 2,
         "today_duplicates": 1, "today_scans": 3}
    assert "• S1: 2" in exporter.summary_text(s, now)
