[app]

title = Material Circulante
# package.name/domain ficam iguais: o APK novo instala por cima do Neon Cart
# e mantém os dados (lista, listas salvas, histórico) que já estão no celular.
package.name = neoncart
package.domain = br.com.neoncart

source.dir = .
source.include_exts = py,kv,png,ttf,json,wav
source.exclude_dirs = tests, bin, .buildozer, .venv, .git, .github, __pycache__
source.exclude_patterns = README.md, requirements-dev.txt

version = 2.1.0

# pyzbar usa a lib nativa libzbar (receita do python-for-android).
# filetype é dependência do Kivy 2.3.1 (kivy.core.image) que o p4a v2024.01.21 não inclui.
requirements = python3,kivy==2.3.1,filetype,pyjnius,android,pillow,libzbar,pyzbar,openpyxl,et_xmlfile

icon.filename = %(source.dir)s/assets/icon.png
presplash.filename = %(source.dir)s/assets/presplash.png
android.presplash_color = #09090b

orientation = portrait
fullscreen = 0

# Câmera para o leitor; vibração no scan; gravação em Downloads só no Android 9 ou anterior.
android.permissions = android.permission.CAMERA, android.permission.VIBRATE, (name=android.permission.WRITE_EXTERNAL_STORAGE;maxSdkVersion=28)

android.api = 34
android.minapi = 24
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
android.allow_backup = True

# Versão estável do python-for-android (Python 3.11). O master usa Python 3.14
# e quebra a instalação das dependências do Kivy via pip.
p4a.branch = v2024.01.21


[buildozer]
log_level = 2
warn_on_root = 1
