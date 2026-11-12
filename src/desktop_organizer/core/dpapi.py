"""Encryption bound to the Windows user account (DPAPI).

Data protected here can only be decrypted by the same Windows user on the same
computer. On other systems (development only) data is stored unchanged and
``AVAILABLE`` is False, so callers can tell the user.
"""

from __future__ import annotations

import sys

AVAILABLE = sys.platform == "win32"
_ENTROPY = b"DesktopOrganizer/clipboard/v1"


if AVAILABLE:
    import ctypes
    from ctypes import wintypes

    class _Blob(ctypes.Structure):
        _fields_ = (("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char)))

    _crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _CRYPTPROTECT_UI_FORBIDDEN = 0x1

    def _blob(data: bytes) -> tuple[_Blob, ctypes.Array[ctypes.c_char]]:
        buffer = ctypes.create_string_buffer(data, len(data))
        return _Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char))), buffer

    def _call(function: object, data: bytes) -> bytes:
        source, _keep = _blob(data)
        entropy, _keep2 = _blob(_ENTROPY)
        result = _Blob()
        ok = function(  # type: ignore[operator]
            ctypes.byref(source),
            None,
            ctypes.byref(entropy),
            None,
            None,
            _CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(result),
        )
        if not ok:
            raise OSError(ctypes.get_last_error(), "DPAPI call failed")
        try:
            return ctypes.string_at(result.pbData, result.cbData)
        finally:
            _kernel32.LocalFree(result.pbData)

    def protect(data: bytes) -> bytes:
        return _call(_crypt32.CryptProtectData, data)

    def unprotect(data: bytes) -> bytes:
        return _call(_crypt32.CryptUnprotectData, data)

else:

    def protect(data: bytes) -> bytes:
        return data

    def unprotect(data: bytes) -> bytes:
        return data
