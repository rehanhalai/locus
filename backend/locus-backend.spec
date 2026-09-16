import os
import importlib.util
from PyInstaller.utils.hooks import collect_submodules, collect_all

hiddenimports = []
hiddenimports += collect_submodules('app')

genai_datas, genai_binaries, genai_hiddenimports = collect_all('onnxruntime_genai')
ort_datas, ort_binaries, ort_hiddenimports = collect_all('onnxruntime')

# Explicitly collect all onnxruntime/capi shared libraries and files
extra_binaries = []
extra_datas = []
ort_spec = importlib.util.find_spec('onnxruntime')
if ort_spec and ort_spec.submodule_search_locations:
    capi_dir = os.path.join(ort_spec.submodule_search_locations[0], 'capi')
    if os.path.exists(capi_dir):
        for f in os.listdir(capi_dir):
            full_path = os.path.join(capi_dir, f)
            if os.path.isfile(full_path):
                extra_binaries.append((full_path, 'onnxruntime/capi'))
                extra_datas.append((full_path, 'onnxruntime/capi'))

all_binaries = genai_binaries + ort_binaries + extra_binaries
all_datas = [
    ('bin', 'bin'),
    ('app/modules/analytics/models', 'app/modules/analytics/models'),
] + genai_datas + ort_datas + extra_datas
all_hiddenimports = list(set(hiddenimports + genai_hiddenimports + ort_hiddenimports))

a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=all_binaries,
    datas=all_datas,
    hiddenimports=all_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='locus-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
