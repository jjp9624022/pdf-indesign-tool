# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for PDF-InDesign 文字替换工具"""

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

a = Analysis(
    ['pdf_analyzer.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('config.example.json', '.'),
        ('prompts.json', '.'),
    ],
    hiddenimports=[
        'PIL',
        'PIL.Image',
        'fitz',
        'customtkinter',
        'tkinter',
        'tkinter.ttk',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'rapidocr_onnxruntime',
        'indesign_client',
        'config_manager',
        'ocr_client',
        'text_editor',
        'pdf_analyzer',
        'pdf_analyzer.main_app',
        'pdf_analyzer.canvas_page',
        'pdf_analyzer.constants',
        'pdf_analyzer.prompt_manager',
        'pdf_analyzer.utils',
        'pdf_analyzer.components',
        'pdf_analyzer.components.ui_builder',
        'pdf_analyzer.components.pdf_controller',
        'pdf_analyzer.components.ocr_handler',
        'pdf_analyzer.components.box_manager',
        'pdf_analyzer.components.indesign_handler',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'scipy',
        'numpy.testing',
        'pytest',
        'setuptools',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='PDF-InDesign-Tool',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
