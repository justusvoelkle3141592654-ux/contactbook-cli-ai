import pytest

from desktop_organizer.core.safety import PathVerdict, classify

ENV = {
    "SystemRoot": r"C:\Windows",
    "ProgramFiles": r"C:\Program Files",
    "ProgramFiles(x86)": r"C:\Program Files (x86)",
    "ProgramData": r"C:\ProgramData",
    "USERPROFILE": r"C:\Users\anna",
}


@pytest.mark.parametrize(
    ("path", "verdict"),
    [
        (r"C:\Users\anna\Downloads", PathVerdict.ALLOWED),
        (r"c:/users/ANNA/Documents/Ünïcode folder", PathVerdict.ALLOWED),
        (r"D:\Backups", PathVerdict.ALLOWED),
        (r"\\server\share\photos", PathVerdict.ALLOWED),
        (r"C:\Windows", PathVerdict.SYSTEM),
        (r"c:\windows\System32\drivers", PathVerdict.SYSTEM),
        (r"C:\Program Files\App", PathVerdict.SYSTEM),
        (r"C:\Program Files (x86)", PathVerdict.SYSTEM),
        (r"C:\ProgramData\x", PathVerdict.SYSTEM),
        (r"C:\Users\bob\Documents", PathVerdict.OTHER_USER),
        (r"C:\Users", PathVerdict.OTHER_USER),
        (r"C:\Users\anna2", PathVerdict.OTHER_USER),
        (r"C:\WindowsApps-not-system", PathVerdict.ALLOWED),
        ("C:\\", PathVerdict.DRIVE_ROOT),
        ("D:", PathVerdict.DRIVE_ROOT),
        (r"C:\Users\anna\..\bob", PathVerdict.OTHER_USER),
    ],
)
def test_classify(path: str, verdict: PathVerdict) -> None:
    assert classify(path, ENV) is verdict
