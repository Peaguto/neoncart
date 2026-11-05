[app]

title = Neon Cart
package.name = neoncart
package.domain = br.com.neoncart

source.dir = .
source.include_exts = py,kv,png,ttf,json
source.exclude_dirs = tests, bin, .buildozer, .venv, .git, __pycache__
source.exclude_patterns = README.md, requirements-dev.txt

version = 1.0.0

# pyzbar usa a lib nativa libzbar (receita do python-for-android).
requirements = python3,kivy==2.3.1,pyjnius,android,pillow,libzbar,pyzbar,openpyxl,et_xmlfile

icon.filename = %(source.dir)s/assets/icon.png
presplash.filename = %(source.dir)s/assets/presplash.png
android.presplash_color = #09090b

orientation = portrait
fullscreen = 0

# Câmera para o leitor; gravação em Downloads só é pedida no Android 9 ou anterior.
android.permissions = android.permission.CAMERA, (name=android.permission.WRITE_EXTERNAL_STORAGE;maxSdkVersion=28)

android.api = 34
android.minapi = 24
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
android.allow_backup = True


[buildozer]
log_level = 2
warn_on_root = 1
