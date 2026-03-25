# macro_quick_access.spec — PyInstaller spec para Macro Quick Access
# Generado para Windows. Ejecutar con: pyinstaller macro_quick_access.spec --clean

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('icon_collapsed.png', '.'),
    ],
    hiddenimports=[
        'win32gui',
        'win32con',
        'win32api',
        'win32process',
        'pynput.keyboard._win32',
        'pynput.mouse._win32',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MacroQuickAccess',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # Sin ventana de consola negra
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,              # Agregar ruta a un .ico para personalizar el icono del exe
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MacroQuickAccess',
)
