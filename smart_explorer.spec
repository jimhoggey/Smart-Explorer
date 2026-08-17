# -*- mode: python ; coding: utf-8 -*-
import sys
from PyInstaller.utils.hooks import collect_data_files

icon = "assets/icon.ico" if sys.platform == "win32" else "assets/icon.icns"
a = Analysis(["desktop.py"], datas=[("static", "static")] + collect_data_files("imageio_ffmpeg"))
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, exclude_binaries=True, name="SmartExplorer", console=False, icon=icon)
coll = COLLECT(exe, a.binaries, a.datas, name="SmartExplorer")
if sys.platform == "darwin":
    app = BUNDLE(coll, name="SmartExplorer.app", icon=icon,
                 bundle_identifier="com.jimhoggey.smartexplorer",
                 info_plist={"NSHighResolutionCapable": True, "LSApplicationCategoryType": "public.app-category.utilities"})
