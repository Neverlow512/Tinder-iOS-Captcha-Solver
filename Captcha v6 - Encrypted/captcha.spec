# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(['captcha_solver.py'],
             pathex=['.'],
             binaries=[],
             datas=[],
             hiddenimports=['pytesseract', 'PIL', 'cryptography', 'appium', 'selenium', 'requests'],
             hookspath=[],
             hooksconfig={},
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)

pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)

exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='captcha_solver',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=True )

coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               upx_exclude=[],
               name='captcha_solver')
