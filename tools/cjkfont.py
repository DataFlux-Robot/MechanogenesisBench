#!/usr/bin/env python3
"""Register Noto Sans CJK SC with matplotlib.

matplotlib's font manager only indexes the first face of a .ttc collection
(JP on this system), so the SC faces are extracted with fontTools on demand.
"""
from pathlib import Path
from matplotlib import font_manager

CACHE = Path('/tmp/matplotlib_cjk')
FACES = {'Regular': CACHE / 'NotoSansCJKsc-Regular.otf',
         'Bold': CACHE / 'NotoSansCJKsc-Bold.otf'}
TTC = '/usr/share/fonts/opentype/noto/NotoSansCJK-{style}.ttc'


def register() -> str:
    """Extract (if needed) and register the SC faces; return family name."""
    need = [s for s, p in FACES.items() if not p.exists()]
    if need:
        from fontTools.ttLib import TTCollection
        CACHE.mkdir(parents=True, exist_ok=True)
        for style in need:
            ttc = TTCollection(TTC.format(style=style), lazy=True)
            for f in ttc.fonts:
                if f['name'].getDebugName(1) == 'Noto Sans CJK SC':
                    f.save(str(FACES[style]))
                    break
    for p in FACES.values():
        font_manager.fontManager.addfont(str(p))
    return 'Noto Sans CJK SC'
