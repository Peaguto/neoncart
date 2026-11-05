"""Integração com o Android (pyjnius), com alternativas para o desktop."""

import os
import shutil
import urllib.parse
import webbrowser

from kivy.utils import platform

IS_ANDROID = platform == "android"

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
JSON_MIME = "application/json"
PICK_REQUEST_CODE = 0x4E43  # "NC"

if IS_ANDROID:
    from android.runnable import run_on_ui_thread  # noqa: F401  (p4a)
    from jnius import autoclass, cast

    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    Intent = autoclass("android.content.Intent")
    JString = autoclass("java.lang.String")
    BuildVersion = autoclass("android.os.Build$VERSION")
    Environment = autoclass("android.os.Environment")
    AndroidCamera = autoclass("android.hardware.Camera")
    CameraInfo = autoclass("android.hardware.Camera$CameraInfo")
else:  # desktop: executa direto
    def run_on_ui_thread(fn):
        return fn


def _activity():
    return PythonActivity.mActivity


def _char_seq(text):
    return cast("java.lang.CharSequence", JString(text))


# --- permissões --------------------------------------------------------
def request_camera_permission(callback):
    """Chama callback(True/False) depois de pedir a permissão de câmera."""
    if not IS_ANDROID:
        callback(True)
        return
    from android.permissions import Permission, check_permission, request_permissions

    if check_permission(Permission.CAMERA):
        callback(True)
        return

    def _done(permissions, results):
        callback(bool(results) and all(results))

    request_permissions([Permission.CAMERA], _done)


def request_storage_permission():
    """Android 9 ou anterior precisa de permissão para gravar em Downloads."""
    if IS_ANDROID and BuildVersion.SDK_INT < 29:
        from android.permissions import Permission, check_permission, request_permissions

        if not check_permission(Permission.WRITE_EXTERNAL_STORAGE):
            request_permissions([Permission.WRITE_EXTERNAL_STORAGE])


# --- compartilhar ------------------------------------------------------
@run_on_ui_thread
def _start_chooser(intent, title):
    chooser = Intent.createChooser(intent, _char_seq(title))
    _activity().startActivity(chooser)


def share_text(text, title="Relatório de Carrinhos"):
    if IS_ANDROID:
        intent = Intent()
        intent.setAction(Intent.ACTION_SEND)
        intent.setType("text/plain")
        intent.putExtra(Intent.EXTRA_SUBJECT, JString(title))
        intent.putExtra(Intent.EXTRA_TEXT, _char_seq(text))
        _start_chooser(intent, title)
        return
    webbrowser.open("https://wa.me/?text=" + urllib.parse.quote(text))


def share_file(uri, mime, title="Relatório de Carrinhos"):
    """Compartilha um arquivo já salvo pelo MediaStore (content://)."""
    if not IS_ANDROID or uri is None:
        return False
    intent = Intent()
    intent.setAction(Intent.ACTION_SEND)
    intent.setType(mime)
    intent.putExtra(Intent.EXTRA_STREAM, cast("android.os.Parcelable", uri))
    intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
    _start_chooser(intent, title)
    return True


# --- salvar em Downloads -----------------------------------------------
def save_to_downloads(src_path, filename, mime=XLSX_MIME):
    """Copia o arquivo para a pasta Downloads.

    Retorna (descrição_do_local, uri_ou_None).
    """
    if not IS_ANDROID:
        folder = os.path.join(os.path.expanduser("~"), "Downloads")
        os.makedirs(folder, exist_ok=True)
        dest = os.path.join(folder, filename)
        shutil.copyfile(src_path, dest)
        return dest, None

    if BuildVersion.SDK_INT >= 29:
        ContentValues = autoclass("android.content.ContentValues")
        Downloads = autoclass("android.provider.MediaStore$Downloads")
        MediaColumns = autoclass("android.provider.MediaStore$MediaColumns")

        values = ContentValues()
        values.put(MediaColumns.DISPLAY_NAME, JString(filename))
        values.put(MediaColumns.MIME_TYPE, JString(mime))
        values.put(MediaColumns.RELATIVE_PATH, JString(Environment.DIRECTORY_DOWNLOADS))
        resolver = _activity().getContentResolver()
        uri = resolver.insert(Downloads.EXTERNAL_CONTENT_URI, values)
        if uri is None:
            raise OSError("Não foi possível criar o arquivo em Downloads")
        out = resolver.openOutputStream(uri)
        try:
            with open(src_path, "rb") as fh:
                out.write(fh.read())
            out.flush()
        finally:
            out.close()
        return "Downloads/" + filename, uri

    folder = Environment.getExternalStoragePublicDirectory(
        Environment.DIRECTORY_DOWNLOADS).getAbsolutePath()
    os.makedirs(folder, exist_ok=True)
    dest = os.path.join(folder, filename)
    shutil.copyfile(src_path, dest)
    return dest, None


# --- câmera ------------------------------------------------------------
def camera_count():
    if IS_ANDROID:
        return AndroidCamera.getNumberOfCameras()
    return 1


def back_camera_index():
    """Índice da câmera traseira (ou 0)."""
    if not IS_ANDROID:
        return 0
    info = CameraInfo()
    for i in range(AndroidCamera.getNumberOfCameras()):
        AndroidCamera.getCameraInfo(i, info)
        if info.facing == CameraInfo.CAMERA_FACING_BACK:
            return i
    return 0


def camera_display(index):
    """Retorna (ângulo, espelhar) para mostrar a prévia em retrato."""
    if not IS_ANDROID:
        return 0, False
    info = CameraInfo()
    AndroidCamera.getCameraInfo(index, info)
    if info.facing == CameraInfo.CAMERA_FACING_FRONT:
        return info.orientation, True
    return -info.orientation, False


def set_torch(camera_widget, on):
    """Liga/desliga o flash. Retorna False se não houver suporte."""
    core = getattr(camera_widget, "_camera", None)
    android_cam = getattr(core, "_android_camera", None)
    if android_cam is None:
        return False
    try:
        params = android_cam.getParameters()
        modes = params.getSupportedFlashModes()
        if modes is None or not modes.contains("torch"):
            return False
        params.setFlashMode("torch" if on else "off")
        android_cam.setParameters(params)
        return True
    except Exception:  # noqa: BLE001 - qualquer erro do driver = sem flash
        return False


def release_camera(camera_widget):
    """Para e libera a câmera (o widget do Kivy não libera sozinho)."""
    if camera_widget is None:
        return
    core = getattr(camera_widget, "_camera", None)
    try:
        camera_widget.play = False
    except Exception:  # noqa: BLE001
        pass
    if core is None:
        return
    try:
        core.stop()
    except Exception:  # noqa: BLE001
        pass
    release = getattr(core, "_release_camera", None)
    if release is not None:
        try:
            release()
        except Exception:  # noqa: BLE001
            pass
    camera_widget._camera = None


# --- vibração ----------------------------------------------------------
def vibrate(ms=60):
    if not IS_ANDROID:
        return
    try:
        Context = autoclass("android.content.Context")
        service = _activity().getSystemService(Context.VIBRATOR_SERVICE)
        vibrator = cast("android.os.Vibrator", service)
        if not vibrator.hasVibrator():
            return
        if BuildVersion.SDK_INT >= 26:
            VibrationEffect = autoclass("android.os.VibrationEffect")
            vibrator.vibrate(VibrationEffect.createOneShot(int(ms), VibrationEffect.DEFAULT_AMPLITUDE))
        else:
            vibrator.vibrate(int(ms))
    except Exception as exc:  # noqa: BLE001 - vibração é opcional
        print("NeonCart: vibração indisponível:", exc)


# --- escolher arquivo (importar backup) ---------------------------------
def pick_text_file(callback, mime="*/*"):
    """Abre o seletor de arquivos e chama callback(texto_ou_None, nome).

    No desktop, usa o backup mais recente em ~/Downloads.
    """
    if not IS_ANDROID:
        import glob

        folder = os.path.join(os.path.expanduser("~"), "Downloads")
        files = sorted(glob.glob(os.path.join(folder, "NeonCart_Backup_*.json")),
                       key=os.path.getmtime)
        if not files:
            callback(None, "")
            return
        with open(files[-1], "r", encoding="utf-8") as fh:
            callback(fh.read(), os.path.basename(files[-1]))
        return

    from android import activity

    def _on_result(request_code, result_code, data):
        if request_code != PICK_REQUEST_CODE:
            return
        activity.unbind(on_activity_result=_on_result)
        if result_code != -1 or data is None:  # -1 = RESULT_OK
            callback(None, "")
            return
        uri = data.getData()
        try:
            callback(_read_uri_text(uri), uri.getLastPathSegment() or "")
        except Exception as exc:  # noqa: BLE001
            print("NeonCart: erro ao ler arquivo:", exc)
            callback(None, "")

    activity.bind(on_activity_result=_on_result)
    intent = Intent(Intent.ACTION_OPEN_DOCUMENT)
    intent.addCategory(Intent.CATEGORY_OPENABLE)
    intent.setType(mime)
    _activity().startActivityForResult(intent, PICK_REQUEST_CODE)


def _read_uri_text(uri):
    InputStreamReader = autoclass("java.io.InputStreamReader")
    BufferedReader = autoclass("java.io.BufferedReader")
    stream = _activity().getContentResolver().openInputStream(uri)
    reader = BufferedReader(InputStreamReader(stream, "UTF-8"))
    lines = []
    try:
        while True:
            line = reader.readLine()
            if line is None:
                break
            lines.append(line)
    finally:
        reader.close()
    return "\n".join(lines)
