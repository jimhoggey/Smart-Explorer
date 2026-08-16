# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files

a = Analysis(["desktop.py"], datas=[("static", "static")] + collect_data_files("imageio_ffmpeg"))
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, exclude_binaries=True, name="SmartExplorer", console=False)
coll = COLLECT(exe, a.binaries, a.datas, name="SmartExplorer")
