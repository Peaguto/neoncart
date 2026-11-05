"""Neon Cart - baixa de carrinhos (versão Android em Python/Kivy)."""

import os
import tempfile

from kivy.animation import Animation
from kivy.app import App
from kivy.clock import Clock
from kivy.core.text import Label as CoreLabel
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp, sp
from kivy.properties import (BooleanProperty, ListProperty, NumericProperty,
                             ObjectProperty, StringProperty)
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivy.uix.textinput import TextInput

import exporter
import platform_utils as pu
from scanner import ScannerModal  # noqa: F401  (usado no .kv)
from storage import DuplicateCodeError, EntryStore, local_datetime
from theme import ICON_FONT, C, I, gradient_texture

APP_DIR = os.path.dirname(os.path.abspath(__file__))
ICON_FONT_PATH = os.path.join(APP_DIR, ICON_FONT)


# --- widgets básicos -----------------------------------------------------
class IconLabel(Label):
    icon = StringProperty("")


class IconButton(ButtonBehavior, Label):
    icon = StringProperty("")
    icon_color = ListProperty(C.purple400)
    hover_bg = ListProperty([0, 0, 0, 0])


class GradientButton(ButtonBehavior, BoxLayout):
    icon = StringProperty("")
    text = StringProperty("")
    texture = ObjectProperty(None, allownone=True)


class NeonInput(TextInput):
    """TextInput com ícone à esquerda e borda neon ao focar."""

    icon = StringProperty("")
    uppercase = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._icon_color = Color(*C.purple600)
        self._icon_rect = Rectangle()
        self.canvas.after.add(self._icon_color)
        self.canvas.after.add(self._icon_rect)
        self.bind(icon=self._render_icon, pos=self._place_icon,
                  size=self._place_icon, focus=self._on_focus_icon)
        Clock.schedule_once(lambda dt: self._render_icon())

    def _render_icon(self, *args):
        if not self.icon:
            self._icon_rect.texture = None
            self._icon_rect.size = (0, 0)
            return
        lbl = CoreLabel(text=self.icon, font_name=ICON_FONT_PATH, font_size=sp(20))
        lbl.refresh()
        self._icon_rect.texture = lbl.texture
        self._icon_rect.size = lbl.texture.size
        self._place_icon()

    def _place_icon(self, *args):
        w, h = self._icon_rect.size
        self._icon_rect.pos = (self.x + dp(14), self.center_y - h / 2)

    def _on_focus_icon(self, *args):
        self._icon_color.rgba = C.pink500 if self.focus else C.purple600

    def insert_text(self, substring, from_undo=False):
        if self.uppercase:
            substring = substring.upper()
        return super().insert_text(substring, from_undo=from_undo)


class EntryRow(RecycleDataViewBehavior, BoxLayout):
    entry_id = StringProperty("")
    code = StringProperty("")
    time = StringProperty("")
    division = StringProperty("")
    observation = StringProperty("")


class DuplicateAlert(BoxLayout):
    code = StringProperty("")


# --- janelas -------------------------------------------------------------
class EditModal(ModalView):
    entry_id = StringProperty("")
    __events__ = ("on_save",)

    def on_save(self, *args):
        pass

    def submit(self):
        self.dispatch("on_save", self.entry_id, self.ids.code.text,
                      self.ids.division.text, self.ids.observation.text)


class ConfirmModal(ModalView):
    title = StringProperty("")
    message = StringProperty("")
    confirm_text = StringProperty("CONFIRMAR")
    confirm_cb = ObjectProperty(None, allownone=True)

    def confirm(self):
        self.dismiss()
        if self.confirm_cb:
            self.confirm_cb()


class InfoModal(ModalView):
    icon = StringProperty(I.alert)
    title = StringProperty("")
    message = StringProperty("")
    action_text = StringProperty("")
    action_cb = ObjectProperty(None, allownone=True)

    def action(self):
        self.dismiss()
        if self.action_cb:
            self.action_cb()


class Root(FloatLayout):
    pass


# --- app -----------------------------------------------------------------
class NeonCartApp(App):
    title = "Neon Cart"
    icon_font = ICON_FONT_PATH
    C = C
    I = I

    total = NumericProperty(0)
    visible = NumericProperty(0)
    search_query = StringProperty("")
    grad_main = ObjectProperty(None, allownone=True)
    grad_alt = ObjectProperty(None, allownone=True)
    grad_header = ObjectProperty(None, allownone=True)

    def build(self):
        Window.clearcolor = C.bg
        Window.softinput_mode = "below_target"
        self.grad_main = gradient_texture("#9333ea", "#db2777")
        self.grad_alt = gradient_texture("#db2777", "#9333ea")
        self.grad_header = gradient_texture("#581c87", "#701a75", "#831843")
        self.store = EntryStore(os.path.join(self.user_data_dir, "entries.json"))
        self.root = Root()
        self.refresh_list()
        Window.bind(width=lambda *a: Clock.schedule_once(lambda dt: self.refresh_list(), 0))
        return self.root

    @property
    def ids(self):
        return self.root.ids

    # --- lista ---------------------------------------------------------
    def on_search_query(self, *args):
        self.refresh_list()

    def _row_height(self, observation, width):
        base = dp(12) * 2 + dp(30) + dp(6) + dp(24)
        if not observation:
            return base
        text_width = max(width - dp(16) * 2 - dp(48) - dp(16), dp(80))
        lbl = CoreLabel(text="OBS: " + observation, font_size=sp(12),
                        text_size=(text_width, None))
        lbl.refresh()
        return base + dp(8) + lbl.texture.size[1] + dp(16)

    def refresh_list(self):
        if self.root is None:
            return
        rows = self.store.filter(self.search_query)
        self.total = len(self.store.entries)
        self.visible = len(rows)
        width = self.ids.rv.width if self.ids.rv.width > 10 else Window.width - dp(32)
        data = []
        for e in rows:
            obs = e.get("observation") or ""
            data.append({
                "entry_id": e["id"],
                "code": e["code"],
                "time": local_datetime(e).strftime("%H:%M"),
                "division": e["division"],
                "observation": obs,
                "height": self._row_height(obs, width),
            })
        self.ids.rv.data = data

    # --- formulário ----------------------------------------------------
    def submit(self):
        code_in, div_in, obs_in = self.ids.code, self.ids.division, self.ids.observation
        try:
            entry = self.store.add(code_in.text, div_in.text, obs_in.text)
        except DuplicateCodeError as exc:
            code_in.text = ""
            obs_in.text = ""
            self.show_duplicate(exc.code)
            self._focus(code_in)
            return
        if entry is None:
            # Campo obrigatório vazio: foca o primeiro que falta.
            self._focus(div_in if not div_in.text.strip() else code_in)
            return
        code_in.text = ""
        obs_in.text = ""
        self.refresh_list()
        self._focus(code_in)

    def _focus(self, widget):
        Clock.schedule_once(lambda dt: setattr(widget, "focus", True), 0.1)

    def show_duplicate(self, code):
        alert = self.ids.dup_alert
        alert.code = code
        Animation.cancel_all(alert)
        top_y = self.root.top - dp(24) - alert.height
        alert.y = self.root.top
        alert.opacity = 0
        anim = (Animation(y=top_y, opacity=1, d=0.3, t="out_expo")
                + Animation(d=2.4)
                + Animation(y=self.root.top, opacity=0, d=0.3, t="in_cubic"))
        anim.start(alert)

    # --- câmera --------------------------------------------------------
    def open_scanner(self):
        modal = ScannerModal()
        modal.bind(on_result=self._on_scanned)
        modal.open()

    def _on_scanned(self, modal, code):
        self.ids.code.text = code.upper()
        self._focus(self.ids.code)

    # --- edição / exclusão ---------------------------------------------
    def edit_entry(self, entry_id):
        entry = self.store.get(entry_id)
        if entry is None:
            return
        modal = EditModal(entry_id=entry_id)
        modal.ids.code.text = entry["code"]
        modal.ids.division.text = entry["division"]
        modal.ids.observation.text = entry.get("observation") or ""
        modal.bind(on_save=self._save_edit)
        modal.open()

    def _save_edit(self, modal, entry_id, code, division, observation):
        try:
            updated = self.store.update(entry_id, code, division, observation)
        except DuplicateCodeError as exc:
            self.show_info("CÓDIGO DUPLICADO",
                           "O código {} já está registrado em outro carrinho!".format(exc.code))
            return
        if updated is None:
            return
        modal.dismiss()
        self.refresh_list()

    def remove_entry(self, entry_id):
        def _do():
            self.store.remove(entry_id)
            self.refresh_list()
        self.confirm("EXCLUIR", "Excluir este carrinho?", _do, "EXCLUIR")

    def clear_all(self):
        def _do():
            self.store.clear()
            self.search_query = ""
            self.ids.search.text = ""
            self.refresh_list()
        self.confirm("LIMPAR SISTEMA",
                     "Tem certeza que deseja apagar TODOS os registros?", _do, "APAGAR TUDO")

    def confirm(self, title, message, callback, confirm_text="CONFIRMAR"):
        ConfirmModal(title=title, message=message, confirm_cb=callback,
                     confirm_text=confirm_text).open()

    def show_info(self, title, message, action_text="", on_action=None, icon=I.alert):
        InfoModal(title=title, message=message, action_text=action_text,
                  action_cb=on_action, icon=icon).open()

    # --- exportar / compartilhar ----------------------------------------
    def share(self):
        rows = self.store.filter(self.search_query) or self.store.entries
        if not rows:
            return
        try:
            pu.share_text(exporter.share_text(rows))
        except Exception as exc:  # noqa: BLE001
            self.show_info("ERRO", "Não foi possível compartilhar.\n{}".format(exc))

    def export(self):
        entries = self.store.entries
        if not entries:
            return
        pu.request_storage_permission()
        filename = exporter.report_filename()
        tmp_dir = tempfile.mkdtemp(dir=self.user_data_dir)
        tmp_path = os.path.join(tmp_dir, filename)
        try:
            exporter.export_xlsx(entries, tmp_path)
            where, uri = pu.save_to_downloads(tmp_path, filename)
        except Exception as exc:  # noqa: BLE001
            self.show_info("ERRO", "Não foi possível exportar.\n{}".format(exc))
            return
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            os.rmdir(tmp_dir)
        if uri is not None:
            self.show_info("EXPORTADO", "Planilha salva em:\n" + where, "COMPARTILHAR",
                           lambda: pu.share_file(uri, pu.XLSX_MIME), icon=I.download)
        else:
            self.show_info("EXPORTADO", "Planilha salva em:\n" + where, icon=I.download)


if __name__ == "__main__":
    NeonCartApp().run()
