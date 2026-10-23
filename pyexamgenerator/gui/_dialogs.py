"""The ``messagebox`` of the application, shared by the window and every tab."""

from tkinter import messagebox as tkinter_messagebox
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from pyexamgenerator.main_app import ExamApp


class _CopyableMessageBox:
    """``messagebox`` of the application: info/warning/error popups use the app's copyable dialog.

    Everything else (askyesno, ...) is the standard ``tkinter.messagebox``. Before, ExamApp replaced
    ``tkinter.messagebox.show*`` for the whole process, also for any other Tk code in it.
    """

    def __init__(self) -> None:
        self.app: Optional["ExamApp"] = None

    def _show(self, kind: str, title=None, message=None, **kwargs):
        if self.app is None:
            return getattr(tkinter_messagebox, f"show{kind}")(title, message, **kwargs)
        return self.app._show_copyable_messagebox(kind=kind, title=title, message=message, **kwargs)

    def showinfo(self, title=None, message=None, **kwargs):
        return self._show("info", title, message, **kwargs)

    def showwarning(self, title=None, message=None, **kwargs):
        return self._show("warning", title, message, **kwargs)

    def showerror(self, title=None, message=None, **kwargs):
        return self._show("error", title, message, **kwargs)

    def __getattr__(self, name):
        return getattr(tkinter_messagebox, name)


messagebox = _CopyableMessageBox()
