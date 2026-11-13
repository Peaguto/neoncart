"""Ponto de entrada do Material Circulante (antigo Neon Cart).

Se o app falhar ao abrir, mostra o erro na tela (em vez de fechar sem
explicação) e grava o relatório em neoncart_crash.txt na pasta do app.
"""

import glob
import os
import sys
import traceback


def _kivy_log_tail(lines=60):
    """Últimas linhas do log do Kivy (ajuda quando o erro é fora do Python)."""
    try:
        from kivy.config import Config
        from kivy.logger import FileHandler  # noqa: F401  (garante o log em arquivo)

        log_dir = Config.get("kivy", "log_dir")
        if not os.path.isabs(log_dir):
            from kivy import kivy_home_dir
            log_dir = os.path.join(kivy_home_dir, log_dir)
        files = sorted(glob.glob(os.path.join(log_dir, "*.txt")), key=os.path.getmtime)
        if not files:
            return ""
        with open(files[-1], "r", encoding="utf-8", errors="replace") as fh:
            return "".join(fh.readlines()[-lines:])
    except Exception:  # noqa: BLE001
        return ""


def _save_report(report):
    base = os.environ.get("ANDROID_PRIVATE") or os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base, "neoncart_crash.txt")
    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(report)
    except OSError:
        path = ""
    return path


def _show_crash(report):
    """App mínimo que só mostra o erro, para o usuário mandar um print."""
    from kivy.app import App
    from kivy.core.clipboard import Clipboard
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.button import Button
    from kivy.uix.label import Label
    from kivy.uix.scrollview import ScrollView

    class CrashApp(App):
        title = "Material Circulante - erro"

        def build(self):
            root = BoxLayout(orientation="vertical", padding=12, spacing=8)
            root.add_widget(Label(
                text="O Material Circulante falhou ao abrir.\nTire um print desta tela e envie ao suporte.",
                size_hint_y=None, height=90, color=(1, 0.5, 0.7, 1), halign="center"))
            scroll = ScrollView()
            label = Label(text=report, size_hint_y=None, font_size="11sp",
                          color=(0.95, 0.95, 0.95, 1), halign="left", valign="top")
            label.bind(width=lambda w, v: setattr(w, "text_size", (v, None)),
                       texture_size=lambda w, v: setattr(w, "height", v[1]))
            scroll.add_widget(label)
            root.add_widget(scroll)
            copy = Button(text="COPIAR ERRO", size_hint_y=None, height=56)
            copy.bind(on_release=lambda *a: Clipboard.copy(report))
            root.add_widget(copy)
            return root

    CrashApp().run()


def run():
    try:
        from neoncart_app import NeonCartApp

        NeonCartApp().run()
    except Exception:  # noqa: BLE001 - qualquer falha vira tela de erro
        report = "Python {}\n\n{}".format(sys.version.split()[0], traceback.format_exc())
        tail = _kivy_log_tail()
        if tail:
            report += "\n--- log do Kivy ---\n" + tail
        print(report)
        path = _save_report(report)
        if path:
            report += "\n(salvo em {})".format(path)
        try:
            _show_crash(report)
        except Exception:  # noqa: BLE001
            traceback.print_exc()
            raise


if __name__ == "__main__":
    run()
