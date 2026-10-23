# pyexamgenerator: A tool for generating exams from PDF files using AI.
# Copyright (C) 2024 Daniel Sánchez-García

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""The application window (ARC-1): menus, status bar, background tasks and the four tabs.

Each tab is a class of its own in :mod:`pyexamgenerator.gui` that receives the app.
:mod:`pyexamgenerator.main_app` keeps exporting :class:`ExamApp` and :func:`main`.
"""

import logging
import tkinter as tk
import webbrowser
from tkinter import ttk, scrolledtext
from pyexamgenerator import credentials, user_config
from pyexamgenerator._console import log_to_console
from pyexamgenerator.gui._dialogs import messagebox
from pyexamgenerator.gui.bank_tab import BankTab
from pyexamgenerator.gui.exam_tab import ExamTab
from pyexamgenerator.gui.grading_tab import GradingTab
from pyexamgenerator.gui.questions_tab import QuestionsTab
import os
import threading

# Importamos la versión directamente desde nuestro paquete
from pyexamgenerator import __version__

from typing import Optional, Dict, Tuple, Any

logger = logging.getLogger(__name__)


class ExamApp:
    """
    Main application for the Exam Generator Suite.

    This class builds the graphical user interface (GUI) using Tkinter,
    and orchestrates the interactions between the user and the backend modules
    (QuestionGenerator, pyexamgenerator, QuestionBankManager).

    Attributes:
        root (tk.Tk): The main window of the application.
        notebook (ttk.Notebook): The widget for managing the application's tabs.
        status_text (tk.StringVar): Variable for the status bar text.
        status_label (ttk.Label): Label for the status bar.
        questions_tab (~pyexamgenerator.gui.questions_tab.QuestionsTab): The «Generar Preguntas» tab, with
            its own variables and actions (ARC-1), the API key and the prompt types among them.
        bank_tab (~pyexamgenerator.gui.bank_tab.BankTab): The «Gestionar Banco de Preguntas» tab.
        exam_tab (~pyexamgenerator.gui.exam_tab.ExamTab): The «Generar Exámenes» tab.
        grading_tab (~pyexamgenerator.gui.grading_tab.GradingTab): The «Corregir Exámenes» tab.
    """

    def __init__(self, root: tk.Tk) -> None:
        """
        Initializes the application, setting up the main window, variables, and tabs.

        Args:
            root (tk.Tk): The main application window (tk.Tk instance).
        """
        self.root = root

        # Usamos la variable __version__ importada
        version = __version__

        self.root.title(f"pyexamgenerator v{version}")

        title_font = ("Helvetica", 16, "bold")
        main_title_label = ttk.Label(self.root, text=f"pyexamgenerator v{version}", font=title_font)
        main_title_label.pack(pady=(10, 5), padx=10, anchor='w')

        if os.getenv(credentials.ENV_VAR, "").strip():
            logger.info("Clave API cargada desde la variable de entorno GEMINI_API_KEY.")

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(expand=True, fill='both', padx=10, pady=5)
        self._install_copyable_messageboxes()

        self.status_text = tk.StringVar()
        self.status_label = ttk.Label(root, textvariable=self.status_text, anchor='w')
        self.status_label.pack(side='bottom', fill='x', padx=10, pady=5)
        self.update_status("Aplicación iniciada.")

        # --- Variables for the "Generate Questions" tab ---

        self.questions_tab = QuestionsTab(self)
        self.bank_tab = BankTab(self)
        self.exam_tab = ExamTab(self)
        self.grading_tab = GradingTab(self)

        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Ayuda", menu=help_menu)

        help_menu.add_command(label="Configurar API Key (Ayuda)...", command=self.open_api_key_help)
        help_menu.add_command(label="Abrir carpeta de configuración", command=self.open_config_folder)
        help_menu.add_command(label="Abrir configuración de corrección", command=self.open_grading_settings)
        help_menu.add_separator()
        help_menu.add_command(label="Acerca de...", command=self.show_about_dialog)

        self.questions_tab._offer_legacy_key_migration()
        self._offer_legacy_config_migration()

    def _install_copyable_messageboxes(self) -> None:
        """Info/warning/error popups of this module use copyable dialogs (see _CopyableMessageBox)."""
        messagebox.app = self

    def _show_copyable_messagebox(self, kind: str, title: Optional[str], message: Optional[str], **kwargs):
        parent = kwargs.get("parent") or self.root
        detail = kwargs.get("detail")
        text = "" if message is None else str(message)
        if detail:
            text = f"{text}\n\n{detail}" if text else str(detail)

        icon = {"info": "[i]", "warning": "[!]", "error": "[x]"}.get(kind, "[*]")
        dialog_title = str(title or "Mensaje")
        top = tk.Toplevel(parent)
        top.title(dialog_title)
        top.transient(parent)
        top.grab_set()
        top.resizable(True, True)
        top.minsize(480, 220)

        body = ttk.Frame(top, padding=10)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text=f"{icon} {dialog_title}", anchor="w").pack(fill="x", pady=(0, 6))

        txt = scrolledtext.ScrolledText(body, wrap=tk.WORD, height=10)
        txt.pack(fill="both", expand=True)
        txt.insert("1.0", text or "")
        txt.configure(state=tk.DISABLED)

        def copy_text(event=None):
            try:
                selected = txt.get("sel.first", "sel.last")
            except tk.TclError:
                selected = text or ""
            top.clipboard_clear()
            top.clipboard_append(selected)
            return "break"

        def close_dialog(event=None):
            top.destroy()
            return "break"

        txt.bind("<Control-c>", copy_text)
        txt.bind("<Control-C>", copy_text)
        top.bind("<Escape>", close_dialog)

        btns = ttk.Frame(body)
        btns.pack(fill="x", pady=(8, 0))
        ttk.Button(btns, text="Copiar", command=copy_text).pack(side="left")
        ttk.Button(btns, text="Cerrar", command=close_dialog).pack(side="right")

        top.protocol("WM_DELETE_WINDOW", close_dialog)
        top.update_idletasks()
        try:
            x = parent.winfo_rootx() + max(0, (parent.winfo_width() - top.winfo_width()) // 2)
            y = parent.winfo_rooty() + max(0, (parent.winfo_height() - top.winfo_height()) // 2)
            top.geometry(f"+{x}+{y}")
        except Exception:
            pass
        txt.focus_set()
        top.wait_window()
        return "ok"

    def open_api_key_help(self):
        """Opens the Google AI documentation for setting up API key environment variables."""
        url = "https://ai.google.dev/gemini-api/docs/api-key?hl=es-419#set-api-env-var"
        try:
            webbrowser.open_new_tab(url)
            self.update_status(f"Abriendo enlace de ayuda en el navegador: {url}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir el enlace en el navegador.\n\nError: {e}")
            self.update_status("Error al intentar abrir el enlace de ayuda.")

    def open_config_folder(self) -> None:
        """Opens the user's configuration folder (custom prompts, exam template) in the file browser."""
        folder = user_config.config_dir()
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            messagebox.showerror("Error", f"No se pudo crear la carpeta de configuración:\n{folder}\n\n{exc}")
            return
        self._open_folder(str(folder))
        messagebox.showinfo(
            "Carpeta de configuración",
            f"Tus prompts personalizados y la plantilla de exámenes se guardan en:\n{folder}",
        )

    def open_grading_settings(self) -> None:
        """Opens grading_settings.json (groups, named topics, PIR rule, Moodle columns; ARC-10).

        The file is first written with the default values (those of the Universidad de Cádiz) if it
        does not exist, so there is something to edit.
        """
        from pyexamgenerator.grading import settings as grading_settings

        try:
            path = grading_settings.write_default_settings()
        except OSError as exc:
            messagebox.showerror("Error", f"No se pudo crear la configuración de corrección:\n{exc}")
            return
        self._open_folder(str(path))
        messagebox.showinfo(
            "Configuración de corrección",
            "Los grupos, los temas con nombre propio, la regla del punto extra (PIR) y los nombres de las "
            f"columnas de Moodle están en:\n{path}\n\nLa corrección usa los cambios la próxima vez que se "
            "ejecute. Si borras el fichero, vuelven los valores de la Universidad de Cádiz.",
        )

    def _offer_legacy_config_migration(self) -> None:
        """ARC-12: older versions kept the prompts and the exam template in the current folder.

        Offers to move them to the user's configuration folder (prompts are merged with the ones
        already there). If the user declines, they stay where they are and are not used.
        """
        legacy = user_config.find_legacy_files()
        if not legacy:
            return
        labels = {
            user_config.PROMPTS_FILE: "prompts personalizados",
            user_config.EXAM_TEMPLATE_FILE: "plantilla de exámenes",
        }
        listed = "\n".join(f"- {path.name} ({labels[path.name]})" for path in legacy)
        question = (
            f"Hay ficheros de configuración de una versión anterior en la carpeta actual:\n{listed}\n\n"
            f"¿Moverlos a tu carpeta de configuración?\n{user_config.config_dir()}\n\n"
            "Los prompts se combinan con los que ya tengas. Si no los mueves, la aplicación no los usará."
        )
        if not messagebox.askyesno("Configuración de una versión anterior", question):
            return
        try:
            moved = user_config.move_legacy_files()
        except (OSError, ValueError) as exc:
            messagebox.showerror("Error", f"No se pudieron mover los ficheros (no se ha borrado ninguno):\n{exc}")
            return
        self.questions_tab.prompt_types = self.questions_tab.load_prompt_types()
        self.questions_tab.update_prompt_type_options()
        message = f"Configuración movida a:\n{user_config.config_dir()}"
        if moved.prompts_kept:
            message += (
                f"\n\n{moved.prompts_kept} prompt(s) de la carpeta actual tenían el mismo nombre que otros "
                "que ya tenías: se han conservado los tuyos."
            )
        messagebox.showinfo("Configuración", message)

    def update_status(self, message: str) -> None:
        """
        Updates the text of the status bar.

        Args:
            message (str): The text to display in the status bar.
        """
        self.status_text.set(message)

    def _create_scrollable_tab(self, title: str, fill_width: bool = False) -> Tuple[tk.Canvas, ttk.Frame]:
        """Adds a notebook tab whose page scrolls vertically and returns ``(canvas, page_frame)``.

        Build the tab inside ``page_frame`` and, once all its widgets exist, call
        :meth:`_bind_page_scroll` with ``canvas`` so the mouse wheel scrolls the page from any of
        them. With ``fill_width`` the page follows the width of the window.
        """
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=title)

        canvas = tk.Canvas(tab)
        scrollbar = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        page = ttk.Frame(canvas)
        page.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        window_id = canvas.create_window((0, 0), window=page, anchor="nw")
        if fill_width:
            canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window_id, width=e.width))
        return canvas, page

    # Widgets that scroll their own content with the mouse wheel.
    _SELF_SCROLLING_WIDGETS = (tk.Text, tk.Listbox, tk.Canvas, ttk.Treeview, tk.Scrollbar, ttk.Scrollbar)

    @classmethod
    def _bind_page_scroll(cls, canvas: tk.Canvas, widget: tk.Misc) -> None:
        """Scrolls the tab ``canvas`` with the mouse wheel over ``widget`` and its descendants.

        Widgets that scroll their own content (tables, text boxes...) keep their wheel: binding
        them as well, with "break", stopped them from scrolling (models table, prompt text...).
        """

        def on_mousewheel(event):
            delta_units = int(-1 * (event.delta / 120)) if event.delta else 0
            if delta_units == 0:
                delta_units = -1 if event.delta > 0 else 1
            canvas.yview_scroll(delta_units, "units")
            return "break"

        def on_scroll_up(_event):
            canvas.yview_scroll(-1, "units")
            return "break"

        def on_scroll_down(_event):
            canvas.yview_scroll(1, "units")
            return "break"

        def bind_recursively(current):
            if current is not canvas and isinstance(current, cls._SELF_SCROLLING_WIDGETS):
                return
            current.bind("<MouseWheel>", on_mousewheel)
            current.bind("<Button-4>", on_scroll_up)
            current.bind("<Button-5>", on_scroll_down)
            for child in current.winfo_children():
                bind_recursively(child)

        bind_recursively(widget)

    def _run_in_background(self, status_msg: str, work_fn, on_success, on_error, widgets=()) -> None:
        """Runs ``work_fn()`` in a worker thread so the window keeps responding.

        ``widgets`` (e.g. the button that launched the task) stay disabled until the task ends, so
        it cannot be launched twice. ``work_fn`` runs outside the Tk main thread: it must not read
        Tk variables nor touch widgets (read every value before; to ask the user, use
        :meth:`_call_in_main_thread`). Then ``on_success(result)`` or ``on_error(exception)`` runs
        in the main thread and the widgets are enabled again in every case.
        """
        for widget in widgets:
            widget.configure(state="disabled")
        self.update_status(status_msg)

        def finish(callback, value):
            try:
                callback(value)
            finally:
                for widget in widgets:
                    try:
                        widget.configure(state="normal")
                    except tk.TclError:
                        pass  # the window was closed meanwhile

        def worker():
            try:
                result = work_fn()
            except Exception as exc:  # noqa: BLE001 - handed to on_error in the main thread
                self.root.after(0, lambda e=exc: finish(on_error, e))
            else:
                self.root.after(0, lambda r=result: finish(on_success, r))

        threading.Thread(target=worker, daemon=True).start()

    def _call_in_main_thread(self, fn):
        """Runs ``fn()`` in the Tk main thread and returns its result.

        For worker threads that need to ask the user: dialogs must be created in the main thread.
        The calling thread waits for the answer.
        """
        if threading.current_thread() is threading.main_thread():
            return fn()
        done = threading.Event()
        outcome: Dict[str, Any] = {}

        def run():
            try:
                outcome["value"] = fn()
            except Exception as exc:  # noqa: BLE001 - re-raised in the calling thread
                outcome["error"] = exc
            finally:
                done.set()

        self.root.after(0, run)
        done.wait()
        if "error" in outcome:
            raise outcome["error"]
        return outcome.get("value")

    @staticmethod
    def _open_folder(path: str) -> None:
        """Opens ``path``, a folder in the file browser or a file with its program (Windows only;
        ignored elsewhere)."""
        try:
            os.startfile(path)  # type: ignore[attr-defined]
        except Exception:
            pass

    def show_about_dialog(self):
        """Displays an 'About' dialog with program and license information."""
        about_text = (
            "pyexamgenerator\n\n"
            "Copyright (C) 2024 Daniel Sánchez-García\n\n"
            "Este programa es software libre: usted puede redistribuirlo y/o modificarlo "
            "bajo los términos de la Licencia Pública General de GNU publicada por la "
            "Free Software Foundation, ya sea la versión 3 de la Licencia, o "
            "(a su opción) cualquier versión posterior.\n\n"
            "Este programa se distribuye con la esperanza de que sea útil, pero SIN NINGUNA GARANTÍA; "
            "sin siquiera la garantía implícita de COMERCIABILIDAD o APTITUD PARA UN PROPÓSITO PARTICULAR. "
            "Consulte la Licencia Pública General de GNU para más detalles."
        )
        messagebox.showinfo("Acerca de pyexamgenerator", about_text, parent=self.root)


def main():
    log_to_console()
    root = tk.Tk()
    _app = ExamApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
