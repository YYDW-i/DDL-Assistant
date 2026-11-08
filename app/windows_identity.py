"""User-level Windows shortcut with System.AppUserModel.ID, using native COM only."""
import ctypes as C
import os
from pathlib import Path
from uuid import UUID
from .reminder.notifier import APP_ID


class GUID(C.Structure):
    _fields_ = [("data", C.c_ubyte * 16)]

    def __init__(self, value):
        super().__init__()
        C.memmove(C.addressof(self), UUID(value).bytes_le, 16)


class PROPERTYKEY(C.Structure):
    _fields_ = [("fmtid", GUID), ("pid", C.c_ulong)]


def register_shortcut(target, arguments="", link_path=None, register_app=True):
    if os.name != "nt":
        raise OSError("Windows only")
    ole = C.OleDLL("ole32")
    hresult = C.c_long
    pointer = C.c_void_p
    ole.CoInitializeEx.argtypes = [pointer, C.c_ulong]
    ole.CoCreateInstance.argtypes = [C.POINTER(GUID), pointer, C.c_ulong, C.POINTER(GUID), C.POINTER(pointer)]
    init_result = ole.CoInitializeEx(None, 2)
    initialized = init_result >= 0
    shell = pointer()
    store = pointer()
    persist = pointer()

    def checked(hr):
        if hr < 0:
            raise OSError(f"Windows COM HRESULT 0x{hr & 0xffffffff:08x}")

    def call(obj, index, argtypes, *args):
        table = C.cast(obj, C.POINTER(C.POINTER(pointer))).contents
        method = C.WINFUNCTYPE(hresult, pointer, *argtypes)(table[index])
        checked(method(obj, *args))

    link = Path(link_path) if link_path else Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs/DDL Assistant.lnk"
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        checked(ole.CoCreateInstance(C.byref(GUID("00021401-0000-0000-C000-000000000046")), None, 1,
                                    C.byref(GUID("000214F9-0000-0000-C000-000000000046")), C.byref(shell)))
        call(shell, 20, [C.c_wchar_p], str(Path(target).resolve()))
        call(shell, 11, [C.c_wchar_p], arguments)
        call(shell, 9, [C.c_wchar_p], str(Path(target).resolve().parent))
        call(shell, 7, [C.c_wchar_p], "DDL Assistant 本地任务管理器")
        call(shell, 0, [C.POINTER(GUID), C.POINTER(pointer)], C.byref(GUID("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99")), C.byref(store))
        key = PROPERTYKEY(GUID("9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3"), 5)
        variant = C.create_string_buffer(24)
        # VT_LPWSTR; SetValue copies the string. Python owns this temporary buffer.
        value = C.create_unicode_buffer(APP_ID)
        C.c_ushort.from_buffer(variant).value = 31
        C.c_void_p.from_buffer(variant, 8).value = C.cast(value, pointer).value
        call(store, 6, [C.POINTER(PROPERTYKEY), pointer], C.byref(key), C.byref(variant))
        call(store, 7, [])
        call(shell, 0, [C.POINTER(GUID), C.POINTER(pointer)], C.byref(GUID("0000010b-0000-0000-C000-000000000046")), C.byref(persist))
        call(persist, 6, [C.c_wchar_p, C.c_int], str(link), 1)
        if register_app:
            import winreg
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, f"Software\\Classes\\AppUserModelId\\{APP_ID}") as reg:
                winreg.SetValueEx(reg, "DisplayName", 0, winreg.REG_SZ, "DDL Assistant")
    finally:
        for obj in (persist, store, shell):
            if obj:
                table = C.cast(obj, C.POINTER(C.POINTER(pointer))).contents
                C.WINFUNCTYPE(C.c_ulong, pointer)(table[2])(obj)
        if initialized:
            ole.CoUninitialize()
    return link
