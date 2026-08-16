from __future__ import annotations
 
import ctypes
import sys
from pathlib import Path
 
_loaded_families: dict[str, str] = {}
 
 
def _extract_family_name(font_path: Path) -> str | None:
    """Read the font's internal family name via fontTools, if available."""
    try:
        from fontTools.ttLib import TTFont
    except ImportError:
        return None
 
    try:
        tt = TTFont(font_path, lazy=True)
        name_table = tt["name"]
        # Prefer the "Typographic Family" (nameID 16), fall back to the
        # standard Family name (nameID 1).
        for name_id in (16, 1):
            record = name_table.getName(name_id, 3, 1, 0x409)  # Windows, English
            if record is None:
                record = name_table.getName(name_id, 1, 0, 0)  # Mac, English
            if record is not None:
                return str(record).strip()
    except Exception:
        return None
    return None
 
 
def _register_windows(font_path: Path) -> bool:
    try:
        FR_PRIVATE = 0x10
        added = ctypes.windll.gdi32.AddFontResourceExW(str(font_path), FR_PRIVATE, 0)
        return added > 0
    except Exception:
        return False
 
 
def _register_macos(font_path: Path) -> bool:
    try:
        from ctypes import util
 
        core_text = ctypes.cdll.LoadLibrary(util.find_library("CoreText"))
        core_foundation = ctypes.cdll.LoadLibrary(util.find_library("CoreFoundation"))
 
        core_foundation.CFURLCreateWithFileSystemPath.restype = ctypes.c_void_p
        core_foundation.CFStringCreateWithCString.restype = ctypes.c_void_p
 
        cf_path = core_foundation.CFStringCreateWithCString(
            None, str(font_path).encode("utf-8"), 0x08000100
        )
        cf_url = core_foundation.CFURLCreateWithFileSystemPath(None, cf_path, 0, False)
 
        core_text.CTFontManagerRegisterFontsForURL.restype = ctypes.c_bool
        error_ptr = ctypes.c_void_p()
        ok = core_text.CTFontManagerRegisterFontsForURL(cf_url, 1, ctypes.byref(error_ptr))
        return bool(ok)
    except Exception:
        return False
 
 
def _register_linux(font_path: Path) -> bool:
    try:
        from ctypes import util
 
        fontconfig = ctypes.CDLL(util.find_library("fontconfig") or "libfontconfig.so.1")
        fontconfig.FcInit()
        added = fontconfig.FcConfigAppFontAddFile(None, str(font_path).encode("utf-8"))
        return bool(added)
    except Exception:
        return False
 
 
def load_custom_font(font_path: Path | str) -> str | None:
    """Register a .ttf file for the current process only and return its
    family name for use in Tkinter font tuples. Returns None if the font
    could not be loaded (caller should fall back to a system font)."""
 
    font_path = Path(font_path)
    cache_key = str(font_path)
    if cache_key in _loaded_families:
        return _loaded_families[cache_key]
 
    if not font_path.exists():
        return None
 
    if sys.platform.startswith("win"):
        registered = _register_windows(font_path)
    elif sys.platform == "darwin":
        registered = _register_macos(font_path)
    else:
        registered = _register_linux(font_path)
 
    if not registered:
        return None
 
    family = _extract_family_name(font_path)
    if family:
        _loaded_families[cache_key] = family
    return family