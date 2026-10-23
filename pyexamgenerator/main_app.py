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

import logging
import tkinter as tk
import webbrowser
from tkinter import ttk, filedialog, scrolledtext, simpledialog
import pandas as pd
from pyexamgenerator import credentials, gui_logic, user_config
from pyexamgenerator._console import log_to_console
from pyexamgenerator.tooltip import ToolTip
from pyexamgenerator.gui._dialogs import messagebox
from pyexamgenerator.gui.bank_tab import BankTab
from pyexamgenerator.gui.exam_tab import ExamTab
from pyexamgenerator.gui.questions_tab import QuestionsTab
import os
import tempfile
import threading

# Importamos la versión directamente desde nuestro paquete
from pyexamgenerator import __version__

from typing import Optional, List, Dict, Tuple, Any

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
        self.create_grading_tab()

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

    def create_grading_tab(self) -> None:
        """Crea la pestaña 'Corregir Exámenes' dividida en secciones independientes, cada una con su botón.

        Secciones: datos comunes + mapeo de columnas, corregir examen(es) (OCR o respuestas Moodle),
        asistencia + justificaciones (opcional), integrar notas, punto extra, nota final ponderada y
        sesión (guardar/cargar). Se mantiene además un botón de 'Pipeline completo'.
        """
        canvas, inner = self._create_scrollable_tab('Corregir Exámenes')

        intro = ttk.Label(
            inner,
            text=(
                "Corrige exámenes de teoría por pasos independientes: corregir (OCR de hojas\n"
                "manuscritas o desde respuestas Moodle), asistencia + justificaciones (opcional),\n"
                "integrar notas, punto extra y nota final ponderada. Cada sección tiene su botón.\n"
                "El OCR requiere el extra:  pip install pyexamgenerator[grading]"
            ),
            justify='left',
        )
        intro.pack(anchor='w', padx=10, pady=8)

        # --- Shared input/output variables ---
        self.grad_enrollment_var = tk.StringVar()
        self.grad_xmls_var = tk.StringVar()
        self.grad_images_var = tk.StringVar()
        self.grad_answers_var = tk.StringVar()
        self.grad_theory_var = tk.StringVar()
        self.grad_attendance_var = tk.StringVar()
        self.grad_schedule_var = tk.StringVar()
        self.grad_justif_var = tk.StringVar()
        self.grad_quizzes_var = tk.StringVar()
        self.grad_out_var = tk.StringVar()
        self.grad_sched_sheet_var = tk.StringVar(value="0")
        self.grad_att_header_var = tk.StringVar(value="3")
        self.grad_forced_var = tk.StringVar()
        # System temp folder, not the Desktop (often synced to the cloud): these are students' scans.
        self.grad_ocr_temp_dir_var = tk.StringVar(value=os.path.join(tempfile.gettempdir(), "pyexamgenerator_temp"))
        self.grad_ocr_grades_var = tk.StringVar()
        self.grad_integrated_var = tk.StringVar()
        self.grad_attquiz_var = tk.StringVar()
        self.grad_append_unmatched_var = tk.BooleanVar(value=True)
        # Column mapping (defaults match the historical hard-coded names).
        self.grad_id_col_var = tk.StringVar(value="Número de ID")
        self.grad_first_col_var = tk.StringVar(value="Nombre")
        self.grad_last_col_var = tk.StringVar(value="Apellido(s)")
        self.grad_email_col_var = tk.StringVar(value="Dirección de correo")
        self.grad_total_col_var = tk.StringVar(value="Calificación/10,00")
        self.grad_sender_col_var = tk.StringVar(value="REMITENTE")
        self.grad_subject_col_var = tk.StringVar(value="ASUNTO")
        self.grad_message_col_var = tk.StringVar(value="MENSAJE")
        # Final grade.
        self.grad_final_mode_var = tk.StringVar(value="by_file")
        self.grad_final_files_var = tk.StringVar()
        self.grad_final_source_var = tk.StringVar()
        self.grad_final_weights_var = tk.StringVar()
        self.grad_final_cap_var = tk.BooleanVar(value=True)
        # Compare / overwrite results.
        self.grad_cmp_existing_var = tk.StringVar()
        self.grad_cmp_new_var = tk.StringVar()
        self.grad_cmp_value_cols_var = tk.StringVar()
        self.grad_cmp_addnew_var = tk.BooleanVar(value=True)
        self.grad_cmp_inplace_var = tk.BooleanVar(value=False)
        # Session.
        self.grad_session_path_var = tk.StringVar()

        def file_row(parent, label, var, tip, multiple=False, directory=False):
            rowf = ttk.Frame(parent)
            rowf.pack(fill='x', padx=4, pady=2)
            lbl = ttk.Label(rowf, text=label, width=28, anchor='w')
            lbl.pack(side='left')
            ToolTip(lbl, text=tip)
            ttk.Entry(rowf, textvariable=var).pack(side='left', fill='x', expand=True, padx=4)
            ttk.Button(rowf, text="…", width=3, command=lambda: self._grad_pick(var, multiple, directory)).pack(
                side='left'
            )

        def text_row(parent, label, var, tip, width=24):
            rowf = ttk.Frame(parent)
            rowf.pack(fill='x', padx=4, pady=1)
            lbl = ttk.Label(rowf, text=label, width=28, anchor='w')
            lbl.pack(side='left')
            ToolTip(lbl, text=tip)
            ttk.Entry(rowf, textvariable=var, width=width).pack(side='left', padx=4)

        # --- Section: common data + column mapping ---
        common = ttk.LabelFrame(inner, text="Datos comunes")
        common.pack(fill='x', padx=8, pady=6)
        file_row(
            common,
            "Matriculados (1+):",
            self.grad_enrollment_var,
            "Listados de matrícula (GIM, GITI-GIE-GIEI…). Puedes elegir varios.",
            multiple=True,
        )
        file_row(
            common,
            "Plantillas Moodle XML (1+):",
            self.grad_xmls_var,
            "XML de Moodle con las respuestas correctas (tipos 1A, 1B…).",
            multiple=True,
        )
        file_row(
            common,
            "Carpeta de salida:",
            self.grad_out_var,
            "Carpeta donde se guardan los resultados de cada sección.",
            directory=True,
        )

        cols = ttk.LabelFrame(inner, text="Mapeo de columnas (nombres en tus xlsx)")
        cols.pack(fill='x', padx=8, pady=6)
        ToolTip(
            cols, text="Define el nombre de las columnas de tus ficheros si no coinciden con los valores por defecto."
        )
        colgrid = ttk.Frame(cols)
        colgrid.pack(fill='x')
        left_cols = ttk.Frame(colgrid)
        left_cols.pack(side='left', fill='x', expand=True)
        right_cols = ttk.Frame(colgrid)
        right_cols.pack(side='left', fill='x', expand=True)
        text_row(left_cols, "Nº de ID:", self.grad_id_col_var, "Columna del identificador del alumno.")
        text_row(left_cols, "Nombre:", self.grad_first_col_var, "Columna del nombre.")
        text_row(left_cols, "Apellidos:", self.grad_last_col_var, "Columna de los apellidos.")
        text_row(left_cols, "Correo:", self.grad_email_col_var, "Columna del correo electrónico.")
        text_row(right_cols, "Nota total:", self.grad_total_col_var, "Columna de la calificación total (Moodle).")
        text_row(
            right_cols, "Remitente (justif.):", self.grad_sender_col_var, "Columna del remitente en justificaciones."
        )
        text_row(right_cols, "Asunto (justif.):", self.grad_subject_col_var, "Columna del asunto del correo.")
        text_row(right_cols, "Mensaje (justif.):", self.grad_message_col_var, "Columna del cuerpo del correo.")

        # --- Section: grade exams ---
        grade_sec = ttk.LabelFrame(inner, text="1. Corregir examen(es)")
        grade_sec.pack(fill='x', padx=8, pady=6)
        file_row(
            grade_sec,
            "Imágenes manuscritas (1+):",
            self.grad_images_var,
            "Fotos/escaneos de las hojas de respuestas (para OCR).",
            multiple=True,
        )
        file_row(
            grade_sec,
            "Tipos forzados (opcional):",
            self.grad_forced_var,
            "Forzar el tipo por imagen si el OCR no lo detecta. Formato: imagen.jpg=1A, otra.jpg=1B",
        )
        forced_table_row = ttk.Frame(grade_sec)
        forced_table_row.pack(fill='x', padx=4, pady=(0, 2))
        ttk.Label(forced_table_row, text="", width=28, anchor='w').pack(side='left')
        ttk.Button(forced_table_row, text="Asignar tipos en tabla...", command=self._grad_open_forced_type_table).pack(
            side='left'
        )
        ttk.Label(forced_table_row, text="(Imagen | Tipo | Ruta)").pack(side='left', padx=8)
        file_row(
            grade_sec,
            "Carpeta temp OCR (fallback):",
            self.grad_ocr_temp_dir_var,
            "Ultimo recurso de lectura: copia temporal de imágenes (se limpia al terminar).",
            directory=True,
        )
        file_row(
            grade_sec,
            "Respuestas Moodle (xlsx):",
            self.grad_answers_var,
            "Alternativa al OCR: respuestas ya digitalizadas en un xlsx (corrección desde Excel).",
        )
        btns_grade = ttk.Frame(grade_sec)
        btns_grade.pack(fill='x', pady=4)
        ttk.Button(btns_grade, text="Corregir desde imágenes (OCR)", command=self.grade_exams_from_images).pack(
            side='left', padx=4
        )
        ttk.Button(btns_grade, text="Corregir desde respuestas (xlsx)", command=self.grade_exams_from_answers).pack(
            side='left', padx=4
        )

        # --- Section: attendance + justifications (optional) ---
        att_sec = ttk.LabelFrame(inner, text="2. Asistencia + justificaciones (opcional)")
        att_sec.pack(fill='x', padx=8, pady=6)
        ToolTip(
            att_sec,
            text="Paso independiente: la asistencia se computa aparte y solo se usa para cruzar/descartar. No es obligatorio.",
        )
        file_row(att_sec, "Asistencias:", self.grad_attendance_var, "Excel de asistencias de Moodle.")
        file_row(att_sec, "Horario:", self.grad_schedule_var, "Excel de horario para cruzar fechas/temas (opcional).")
        file_row(
            att_sec,
            "Justificaciones de faltas:",
            self.grad_justif_var,
            "Excel con las justificaciones (columna del remitente arriba).",
        )
        file_row(
            att_sec,
            "Cuestionarios de clase:",
            self.grad_quizzes_var,
            "Excel de calificaciones de cuestionarios de clase (opcional).",
        )
        text_row(
            att_sec,
            "Hoja del horario:",
            self.grad_sched_sheet_var,
            "Nombre de la hoja del horario, o índice (0 = primera).",
        )
        text_row(
            att_sec,
            "Fila de cabecera asist.:",
            self.grad_att_header_var,
            "Fila (0-based) con los encabezados en el Excel de asistencias.",
        )
        ttk.Button(att_sec, text="Analizar asistencia / justificaciones", command=self.run_attendance_analysis).pack(
            pady=4
        )

        # --- Section: integrate grades ---
        integ_sec = ttk.LabelFrame(inner, text="3. Integrar notas (Moodle + OCR)")
        integ_sec.pack(fill='x', padx=8, pady=6)
        file_row(
            integ_sec,
            "Notas de teoría (Moodle):",
            self.grad_theory_var,
            "Excel de calificaciones de teoría exportado de Moodle.",
        )
        file_row(
            integ_sec,
            "Notas OCR (xlsx):",
            self.grad_ocr_grades_var,
            "Notas manuscritas a integrar. Vacío = '<salida>/calificaciones_manuscritos.xlsx'.",
        )
        append_unmatched_chk = ttk.Checkbutton(
            integ_sec,
            text="Añadir alumnos OCR que no estén en teoría (modo unión)",
            variable=self.grad_append_unmatched_var,
        )
        append_unmatched_chk.pack(anchor="w", padx=6, pady=(0, 4))
        ToolTip(
            append_unmatched_chk,
            text=(
                "Activado (recomendado): une teoría+OCR añadiendo filas OCR no presentes en teoría.\n"
                "Desactivado: modo estricto, bloquea esas filas y las registra en incidencias."
            ),
        )
        ttk.Button(integ_sec, text="Integrar notas", command=self.run_integrate_grades).pack(pady=4)

        # --- Section: theory bonus ---
        bonus_sec = ttk.LabelFrame(inner, text="4. Punto extra / teoría")
        bonus_sec.pack(fill='x', padx=8, pady=6)
        file_row(
            bonus_sec,
            "Teoría integrada (xlsx):",
            self.grad_integrated_var,
            "Notas de teoría ya integradas. Vacío = '<salida>/teoria_integrada.xlsx'.",
        )
        file_row(
            bonus_sec,
            "Asistencia+cuestionarios:",
            self.grad_attquiz_var,
            "Tabla asistencia+cuestionarios. Vacío = '<salida>/asistencias_con_cuestionarios.xlsx'.",
        )
        ttk.Button(bonus_sec, text="Aplicar punto extra", command=self.run_apply_bonus).pack(pady=4)

        # --- Section: weighted final grade ---
        final_sec = ttk.LabelFrame(inner, text="5. Nota final ponderada")
        final_sec.pack(fill='x', padx=8, pady=6)
        mode_row = ttk.Frame(final_sec)
        mode_row.pack(fill='x', padx=4, pady=2)
        ttk.Label(mode_row, text="Modo:", width=28, anchor='w').pack(side='left')
        ttk.Radiobutton(mode_row, text="Por fichero", variable=self.grad_final_mode_var, value="by_file").pack(
            side='left', padx=4
        )
        ttk.Radiobutton(mode_row, text="Por columnas", variable=self.grad_final_mode_var, value="by_column").pack(
            side='left', padx=4
        )
        ttk.Checkbutton(mode_row, text="Tope 10", variable=self.grad_final_cap_var).pack(side='left', padx=12)
        files_row = ttk.Frame(final_sec)
        files_row.pack(fill='x', padx=4, pady=2)
        lbl_ff = ttk.Label(files_row, text="Ficheros|peso[|etiqueta]:", width=28, anchor='w')
        lbl_ff.pack(side='left')
        ToolTip(
            lbl_ff,
            text="Modo por fichero. Separa con ';' y usa '|'. Ej: C:/teoria.xlsx|0.6|Teoria ; C:/practicas.xlsx|0.4|Practicas",
        )
        ttk.Entry(files_row, textvariable=self.grad_final_files_var).pack(side='left', fill='x', expand=True, padx=4)
        ttk.Button(files_row, text="+", width=3, command=self._grad_add_final_file).pack(side='left')
        file_row(
            final_sec,
            "Fichero (por columnas):",
            self.grad_final_source_var,
            "Modo por columnas: xlsx único cuyas columnas se ponderan.",
        )
        wrow = ttk.Frame(final_sec)
        wrow.pack(fill='x', padx=4, pady=2)
        lbl_w = ttk.Label(wrow, text="Columnas|peso:", width=28, anchor='w')
        lbl_w.pack(side='left')
        ToolTip(lbl_w, text="Modo por columnas. Separa con ';' y usa '|'. Ej: Teoria|0.6 ; Practicas|0.4")
        ttk.Entry(wrow, textvariable=self.grad_final_weights_var).pack(side='left', fill='x', expand=True, padx=4)
        ttk.Button(final_sec, text="Calcular nota final", command=self.run_final_grade).pack(pady=4)

        # --- Section: compare / overwrite results ---
        cmp_sec = ttk.LabelFrame(inner, text="6. Comparar / sobrescribir resultados")
        cmp_sec.pack(fill='x', padx=8, pady=6)
        ToolTip(
            cmp_sec,
            text="Compara unas calificaciones o asistencias con una versión previa y, opcionalmente, combina sobrescribiendo con los valores nuevos.",
        )
        file_row(
            cmp_sec,
            "Fichero existente (xlsx):",
            self.grad_cmp_existing_var,
            "Resultados previos (calificaciones o asistencias) con los que comparar.",
        )
        file_row(
            cmp_sec,
            "Fichero nuevo (xlsx):",
            self.grad_cmp_new_var,
            "Resultados recién calculados que se comparan con los previos.",
        )
        text_row(
            cmp_sec,
            "Columnas a comparar:",
            self.grad_cmp_value_cols_var,
            "Opcional: columnas separadas por coma. Vacío = todas las columnas comunes (no identificativas).",
            width=36,
        )
        cmp_opts = ttk.Frame(cmp_sec)
        cmp_opts.pack(fill='x', padx=4, pady=2)
        ttk.Checkbutton(cmp_opts, text="Añadir alumnos nuevos al combinar", variable=self.grad_cmp_addnew_var).pack(
            side='left', padx=4
        )
        ttk.Checkbutton(cmp_opts, text="Reemplazar el fichero existente", variable=self.grad_cmp_inplace_var).pack(
            side='left', padx=12
        )
        cmp_btns = ttk.Frame(cmp_sec)
        cmp_btns.pack(fill='x', pady=4)
        ttk.Button(cmp_btns, text="Comparar (solo informe)", command=lambda: self.run_compare_results(False)).pack(
            side='left', padx=4
        )
        ttk.Button(
            cmp_btns, text="Comparar y combinar (sobrescribir)", command=lambda: self.run_compare_results(True)
        ).pack(side='left', padx=4)

        # --- Section: session ---
        sess_sec = ttk.LabelFrame(inner, text="Sesión (retomar más tarde)")
        sess_sec.pack(fill='x', padx=8, pady=6)
        file_row(
            sess_sec,
            "Archivo de sesión:",
            self.grad_session_path_var,
            "Ruta base de la sesión (.pkl/.json). Cargar rellena rutas y columnas.",
        )
        sess_btns = ttk.Frame(sess_sec)
        sess_btns.pack(fill='x', pady=4)
        ttk.Button(sess_btns, text="Guardar sesión", command=self.save_grading_session).pack(side='left', padx=4)
        ttk.Button(sess_btns, text="Cargar sesión", command=self.load_grading_session).pack(side='left', padx=4)

        # --- Full pipeline (all-in-one, as before) ---
        run_btn = ttk.Button(inner, text="Pipeline completo (todo de una pasada)", command=self.run_grading)
        run_btn.pack(pady=12)

        self._bind_page_scroll(canvas, canvas)

    def _grad_pick(self, var: tk.StringVar, multiple: bool = False, directory: bool = False) -> None:
        """Abre el diálogo adecuado y guarda la(s) ruta(s) en `var` (varias separadas por ';')."""
        if directory:
            path = filedialog.askdirectory()
            if path:
                var.set(path)
        elif multiple:
            paths = filedialog.askopenfilenames()
            if paths:
                var.set(";".join(paths))
        else:
            path = filedialog.askopenfilename()
            if path:
                var.set(path)

    # --- Helpers shared by the grading sections ---
    def _grad_run_async(self, status_msg: str, work_fn, done_msg: str = "Listo.") -> None:
        """Runs ``work_fn`` in a background thread, updating the status bar and reporting result/errors.

        ``work_fn`` runs outside the Tk main thread: it must not read Tk variables nor touch widgets
        (read every value before calling this method; use ``self.root.after`` for UI updates).
        It may return either:
        - a string (success info), or
        - a dict like {"info": "...", "warnings": ["...", ...]}.
        """
        if not self._grad_try_start_job():
            return

        def worker():
            try:
                self.root.after(0, lambda: self.update_status(status_msg))
                result = work_fn()

                result_msg = ""
                warning_msgs: List[str] = []
                if isinstance(result, dict):
                    result_msg = str(result.get("info", "") or "").strip()
                    raw_warnings = result.get("warnings", [])
                    if isinstance(raw_warnings, str):
                        raw_warnings = [raw_warnings]
                    if isinstance(raw_warnings, (list, tuple)):
                        warning_msgs = [str(msg).strip() for msg in raw_warnings if str(msg).strip()]
                elif result:
                    result_msg = str(result)

                self.root.after(0, lambda: self.update_status(done_msg))
                if warning_msgs:
                    warning_text = "\n\n".join(warning_msgs)
                    self.root.after(0, lambda t=warning_text: messagebox.showwarning("Avisos", t))
                if result_msg:
                    self.root.after(0, lambda m=result_msg: messagebox.showinfo("Corrección", m))
            except Exception as exc:  # noqa: BLE001 - surfaced to the user
                err = str(exc)
                self.root.after(0, lambda: self.update_status("Error en la corrección."))
                self.root.after(0, lambda e=err: messagebox.showerror("Error", e))
            finally:
                self.root.after(0, self._grad_finish_job)

        threading.Thread(target=worker, daemon=True).start()

    def _grad_try_start_job(self) -> bool:
        """Marks a grading job as running; returns False (with a warning) if one is already running.

        Two jobs at once wrote into the same output folder, including '_intermedios', which one of
        them deletes while the other is still using it.
        """
        if getattr(self, "_grad_job_running", False):
            messagebox.showwarning(
                "Corrección en curso", "Ya hay una tarea de corrección en marcha. Espera a que termine."
            )
            return False
        self._grad_job_running = True
        return True

    def _grad_finish_job(self) -> None:
        self._grad_job_running = False

    @staticmethod
    def _grad_api(out_dir: Optional[str]):
        from pyexamgenerator.grading import ExamCorrectionAPI

        return ExamCorrectionAPI(default_output_dir=(out_dir or "").strip() or None)

    def _grad_enrollment_list(self):
        return [p for p in self.grad_enrollment_var.get().split(";") if p.strip()]

    @staticmethod
    def _grad_merged_enrollment(enrollment_paths: List[str], out_dir: str) -> str:
        """Merges the enrollment files into ``<out_dir>/matriculados.xlsx`` and returns its path.

        Called from worker threads, so it receives the paths instead of reading the Tk variables.
        """
        from pyexamgenerator.grading import EnrollmentMerger

        if not enrollment_paths:
            raise ValueError("Selecciona al menos un fichero de matriculados.")
        os.makedirs(out_dir, exist_ok=True)
        merged = os.path.join(out_dir, "matriculados.xlsx")
        EnrollmentMerger(enrollment_paths).export(merged)
        return merged

    @staticmethod
    def _open_folder(path: str) -> None:
        """Opens ``path``, a folder in the file browser or a file with its program (Windows only;
        ignored elsewhere)."""
        try:
            os.startfile(path)  # type: ignore[attr-defined]
        except Exception:
            pass

    def _grad_column_fields(self) -> Dict[str, Tuple[tk.StringVar, str]]:
        """Column-name fields of the grading tab: key -> (variable, column used when it is empty)."""
        return {
            "id_col": (self.grad_id_col_var, "Número de ID"),
            "first_name_col": (self.grad_first_col_var, "Nombre"),
            "last_name_col": (self.grad_last_col_var, "Apellido(s)"),
            "email_col": (self.grad_email_col_var, "Dirección de correo"),
            "total_grade_col": (self.grad_total_col_var, "Calificación/10,00"),
            "sender_col": (self.grad_sender_col_var, "REMITENTE"),
            "subject_col": (self.grad_subject_col_var, "ASUNTO"),
            "message_col": (self.grad_message_col_var, "MENSAJE"),
        }

    def _grad_columns(self) -> dict:
        return {key: var.get().strip() or default for key, (var, default) in self._grad_column_fields().items()}

    def _grad_image_paths(self) -> List[str]:
        return [p.strip() for p in self.grad_images_var.get().split(";") if p.strip()]

    def _grad_parse_forced(self) -> dict:
        return gui_logic.parse_forced_types(self.grad_forced_var.get())

    def _grad_open_forced_type_table(self) -> None:
        image_paths = self._grad_image_paths()
        if not image_paths:
            messagebox.showwarning("Sin imágenes", "Selecciona primero una o más imágenes manuscritas.")
            return

        current_forced = self._grad_parse_forced()
        dialog = tk.Toplevel(self.root)
        dialog.title("Tipos forzados por imagen")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.minsize(860, 360)

        wrapper = ttk.Frame(dialog, padding=10)
        wrapper.pack(fill="both", expand=True)

        ttk.Label(
            wrapper,
            text=(
                "Edita el tipo por imagen. Puedes escribir en la caja y aplicar a la selección "
                "o hacer doble clic en la columna 'Tipo asignado'."
            ),
            justify="left",
        ).pack(anchor="w", pady=(0, 6))

        table_wrap = ttk.Frame(wrapper)
        table_wrap.pack(fill="both", expand=True)

        cols = ("image_name", "exam_type", "image_path")
        tree = ttk.Treeview(table_wrap, columns=cols, show="headings", selectmode="extended")
        tree.heading("image_name", text="Imagen")
        tree.heading("exam_type", text="Tipo asignado")
        tree.heading("image_path", text="Ruta")
        tree.column("image_name", width=210, stretch=False)
        tree.column("exam_type", width=120, anchor="center", stretch=False)
        tree.column("image_path", width=620, stretch=True)

        yscroll = ttk.Scrollbar(table_wrap, orient="vertical", command=tree.yview)
        xscroll = ttk.Scrollbar(table_wrap, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)

        tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        table_wrap.rowconfigure(0, weight=1)
        table_wrap.columnconfigure(0, weight=1)

        for path in image_paths:
            name = os.path.basename(path)
            forced_type = (
                current_forced.get(path)
                or current_forced.get(path.replace("\\", "/"))
                or current_forced.get(name)
                or ""
            )
            tree.insert("", "end", values=(name, forced_type, path))

        controls = ttk.Frame(wrapper)
        controls.pack(fill="x", pady=(8, 0))
        ttk.Label(controls, text="Tipo:").pack(side="left")
        type_var = tk.StringVar()
        type_entry = ttk.Entry(controls, textvariable=type_var, width=12)
        type_entry.pack(side="left", padx=(4, 8))

        def apply_selected() -> None:
            selected = tree.selection()
            if not selected:
                messagebox.showwarning("Sin selección", "Selecciona al menos una fila en la tabla.")
                return
            forced_type = type_var.get().strip().upper()
            if not forced_type:
                messagebox.showwarning("Tipo vacío", "Indica un tipo de examen (por ejemplo: A, 1A o 2B).")
                return
            for iid in selected:
                tree.set(iid, "exam_type", forced_type)

        def clear_selected() -> None:
            selected = tree.selection()
            if not selected:
                messagebox.showwarning("Sin selección", "Selecciona al menos una fila en la tabla.")
                return
            for iid in selected:
                tree.set(iid, "exam_type", "")

        def edit_type_cell(event) -> None:
            if tree.identify("region", event.x, event.y) != "cell":
                return
            if tree.identify_column(event.x) != "#2":
                return
            iid = tree.identify_row(event.y)
            if not iid:
                return
            image_name = tree.set(iid, "image_name")
            current = tree.set(iid, "exam_type")
            new_value = simpledialog.askstring(
                "Tipo de examen",
                f"Tipo para '{image_name}':",
                initialvalue=current,
                parent=dialog,
            )
            if new_value is None:
                return
            tree.set(iid, "exam_type", new_value.strip().upper())

        def save_and_close() -> None:
            rows = [tree.item(iid, "values") for iid in tree.get_children("")]
            name_counts: Dict[str, int] = {}
            for row in rows:
                image_name = str(row[0]).strip()
                forced_type = str(row[1]).strip()
                if forced_type:
                    name_counts[image_name] = name_counts.get(image_name, 0) + 1

            parts: List[str] = []
            for row in rows:
                image_name = str(row[0]).strip()
                forced_type = str(row[1]).strip().upper()
                image_path = str(row[2]).strip()
                if not forced_type:
                    continue
                # Si hay imágenes con el mismo nombre, usar ruta completa para desambiguar.
                key = image_path if name_counts.get(image_name, 0) > 1 else image_name
                parts.append(f"{key}={forced_type}")

            self.grad_forced_var.set("; ".join(parts))
            dialog.destroy()

        ttk.Button(controls, text="Aplicar a selección", command=apply_selected).pack(side="left")
        ttk.Button(controls, text="Limpiar selección", command=clear_selected).pack(side="left", padx=(6, 0))
        ttk.Button(controls, text="Guardar", command=save_and_close).pack(side="right")
        ttk.Button(controls, text="Cancelar", command=dialog.destroy).pack(side="right", padx=(0, 6))

        tree.bind("<Double-1>", edit_type_cell)
        type_entry.focus_set()

    def _grad_parse_final_files(self) -> list:
        return gui_logic.parse_final_grade_files(self.grad_final_files_var.get())

    def _grad_parse_weights(self) -> dict:
        return gui_logic.parse_column_weights(self.grad_final_weights_var.get())

    def _grad_add_final_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Añadir examen para la nota final",
            filetypes=[("Archivos Excel", "*.xlsx;*.xls")],
        )
        if not path:
            return
        current = self.grad_final_files_var.get().strip()
        entry = f"{path}|1.0"
        self.grad_final_files_var.set(f"{current} ; {entry}" if current else entry)

    def grade_exams_from_images(self) -> None:
        """Section 1a: OCR of handwritten answer sheets into a grades XLSX."""
        from pyexamgenerator.grading import HAS_OCR, ImageGradingConfig

        # Every Tk variable is read here, in the main thread: work() runs in another thread.
        enrollment = self._grad_enrollment_list()
        xmls = [p for p in self.grad_xmls_var.get().split(";") if p.strip()]
        images = [p for p in self.grad_images_var.get().split(";") if p.strip()]
        out = self.grad_out_var.get().strip()
        if not (enrollment and xmls and images and out):
            messagebox.showerror(
                "Faltan datos", "Necesitas matriculados, plantillas XML, imágenes y carpeta de salida."
            )
            return
        if not HAS_OCR:
            messagebox.showerror(
                "OCR no disponible", "El OCR requiere el extra:\n\npip install pyexamgenerator[grading]"
            )
            return
        cols = self._grad_columns()
        forced = self._grad_parse_forced()
        temp_image_dir = self.grad_ocr_temp_dir_var.get().strip() or None

        def work():
            matric = self._grad_merged_enrollment(enrollment, out)
            cfg = ImageGradingConfig(
                xml_paths=xmls,
                image_paths=images,
                enrollment_path=matric,
                enrollment_paths=enrollment,
                output_answers="respuestas.xlsx",
                output_grades="calificaciones_manuscritos.xlsx",
                output_incidents="incidencias.xlsx",
                output_dir=out,
                forced_type_by_image=forced,
                prompt_missing_type=False,
                interactive_review=False,
                aggressive_recovery=True,
                aggressive_min_ratio=0.10,
                aggressive_min_gap_ratio=0.22,
                aggressive_min_top_vs_second=1.08,
                id_col=cols["id_col"],
                first_name_col=cols["first_name_col"],
                last_name_col=cols["last_name_col"],
                email_col=cols["email_col"],
                temp_image_dir=temp_image_dir,
            )
            api = self._grad_api(out)
            api.grade_from_images(cfg)

            warning_msgs: List[str] = []
            incidents_df = api.results.get("ocr_incidents")
            if isinstance(incidents_df, pd.DataFrame) and not incidents_df.empty:
                warning_msgs.append(
                    "Se detectaron incidencias durante el OCR "
                    f"({len(incidents_df)} fila(s)).\n"
                    f"Revisa: {os.path.join(out, 'incidencias.xlsx')}"
                )

            return {
                "info": f"Corrección OCR completada. Resultados en:\n{out}",
                "warnings": warning_msgs,
            }

        self._grad_run_async("Corrigiendo (OCR de hojas, puede tardar)…", work)

    def grade_exams_from_answers(self) -> None:
        """Section 1b: grade from an already-digitized Moodle answers XLSX."""
        from pyexamgenerator.grading import ExcelGradingConfig

        enrollment = self._grad_enrollment_list()
        xmls = [p for p in self.grad_xmls_var.get().split(";") if p.strip()]
        answers = self.grad_answers_var.get().strip()
        out = self.grad_out_var.get().strip()
        if not (enrollment and xmls and answers and out):
            messagebox.showerror(
                "Faltan datos", "Necesitas matriculados, una plantilla XML, el xlsx de respuestas y carpeta de salida."
            )
            return
        cols = self._grad_columns()

        def work():
            matric = self._grad_merged_enrollment(enrollment, out)
            cfg = ExcelGradingConfig(
                exam_xml_path=xmls[0],
                answers_xlsx_path=answers,
                enrollment_xlsx_path=matric,
                output_path="calificaciones_desde_respuestas.xlsx",
                output_dir=out,
                last_name_col=cols["last_name_col"],
                first_name_col=cols["first_name_col"],
                id_col=cols["id_col"],
                email_col=cols["email_col"],
            )
            api = self._grad_api(out)
            api.grade_from_excel(cfg)
            incidents = api.results.get("answers_grading_incidents")
            return {
                "info": f"Corrección desde respuestas completada. Resultados en:\n{out}",
                "warnings": gui_logic.answer_grading_warnings(
                    len(incidents) if isinstance(incidents, pd.DataFrame) else 0,
                    api.results.get("answers_grading_incidents_path", ""),
                ),
            }

        self._grad_run_async("Corrigiendo desde respuestas…", work)

    def run_attendance_analysis(self) -> None:
        """Section 2: attendance + justifications cross-check (optional, independent step)."""
        from pyexamgenerator.grading import AbsenceJustificationConfig

        enrollment = self._grad_enrollment_list()
        attendance = self.grad_attendance_var.get().strip()
        justif = self.grad_justif_var.get().strip()
        out = self.grad_out_var.get().strip()
        if not (enrollment and attendance and justif and out):
            messagebox.showerror(
                "Faltan datos", "Necesitas matriculados, asistencias, justificaciones y carpeta de salida."
            )
            return
        cols = self._grad_columns()
        schedule = self.grad_schedule_var.get().strip() or None
        quizzes = self.grad_quizzes_var.get().strip() or None
        sheet_raw = self.grad_sched_sheet_var.get().strip()
        schedule_sheet = int(sheet_raw) if sheet_raw.isdigit() else (sheet_raw or 0)
        header_raw = self.grad_att_header_var.get().strip()
        header_row = int(header_raw) if header_raw.lstrip("-").isdigit() else 3

        def work():
            matric = self._grad_merged_enrollment(enrollment, out)
            cfg = AbsenceJustificationConfig(
                attendance_xlsx_path=attendance,
                justifications_xlsx_path=justif,
                enrollment_xlsx_path=matric,
                schedule_xlsx_path=schedule,
                schedule_sheet=schedule_sheet,
                quizzes_xlsx_path=quizzes,
                output_dir=out,
                attendance_header_row=header_row,
                sender_col=cols["sender_col"],
                subject_col=cols["subject_col"],
                message_col=cols["message_col"],
                first_name_col=cols["first_name_col"],
                last_name_col=cols["last_name_col"],
                id_col=cols["id_col"],
                email_col=cols["email_col"],
            )
            summary_df, _detail = self._grad_api(out).process_absence_justifications(cfg)
            summary_path = os.path.join(out, "justificaciones_resumen.xlsx")
            return {
                "info": f"Asistencia/justificaciones analizadas. Resultados en:\n{out}",
                "warnings": gui_logic.justification_warnings(
                    summary_df.to_dict("records"),
                    f"Revisa: {summary_path} (columnas «Revisar», «Candidato_Mas_Parecido» y «Cuenta_Para_Justificar»).",
                ),
            }

        self._grad_run_async("Analizando asistencia y justificaciones…", work)

    def run_integrate_grades(self) -> None:
        """Section 3: overlay OCR grades on the Moodle theory workbook."""
        from pyexamgenerator.grading import OCRIntegrationConfig

        theory = self.grad_theory_var.get().strip()
        out = self.grad_out_var.get().strip()
        if not (theory and out):
            messagebox.showerror("Faltan datos", "Necesitas las notas de teoría (Moodle) y la carpeta de salida.")
            return
        ocr_grades = self.grad_ocr_grades_var.get().strip() or os.path.join(out, "calificaciones_manuscritos.xlsx")
        append_unmatched_students = bool(self.grad_append_unmatched_var.get())
        enrollment = self._grad_enrollment_list()

        def work():
            cfg = OCRIntegrationConfig(
                general_xlsx_path=theory,
                ocr_xlsx_path=ocr_grades,
                output_path="teoria_integrada.xlsx",
                output_dir=out,
                enrollment_paths=enrollment,
                append_unmatched_students=append_unmatched_students,
            )
            api = self._grad_api(out)
            api.integrate_ocr_grades(cfg)

            incidents_path = str(
                api.results.get("ocr_integration_incidents_path")
                or os.path.join(out, "incidencias_integracion_ocr.xlsx")
            )
            warning_msgs = gui_logic.integration_warnings(api.results.get("ocr_integration_summary"), incidents_path)

            ocr_incidents_path = os.path.join(out, "incidencias.xlsx")
            if os.path.exists(ocr_incidents_path):
                try:
                    ocr_incidents_df = pd.read_excel(ocr_incidents_path)
                except Exception:
                    ocr_incidents_df = None
                if isinstance(ocr_incidents_df, pd.DataFrame) and not ocr_incidents_df.empty:
                    warning_msgs.append(
                        "Hay incidencias OCR pendientes de revisar "
                        f"({len(ocr_incidents_df)} fila(s)).\n"
                        f"Revisa: {ocr_incidents_path}"
                    )

            return {
                "info": f"Notas integradas en:\n{out}",
                "warnings": warning_msgs,
            }

        self._grad_run_async("Integrando notas OCR en teoría…", work)

    def run_apply_bonus(self) -> None:
        """Section 4: apply the theory bonus point from attendance + quizzes."""
        from pyexamgenerator.grading import TheoryBonusConfig

        out = self.grad_out_var.get().strip()
        if not out:
            messagebox.showerror("Faltan datos", "Necesitas la carpeta de salida.")
            return
        integrated = self.grad_integrated_var.get().strip() or os.path.join(out, "teoria_integrada.xlsx")
        attquiz = self.grad_attquiz_var.get().strip() or os.path.join(out, "asistencias_con_cuestionarios.xlsx")
        theory_grade_col = self.grad_total_col_var.get().strip() or None

        def work():
            cfg = TheoryBonusConfig(
                theory_xlsx_path=integrated,
                attendance_quiz_xlsx_path=attquiz,
                output_path="calificaciones_examen_teoria.xlsx",
                output_dir=out,
                theory_grade_col=theory_grade_col,
                cap_to_10=True,
            )
            self._grad_api(out).apply_theory_bonus(cfg)
            return f"Punto extra aplicado. Resultados en:\n{out}"

        self._grad_run_async("Aplicando punto extra…", work)

    def run_final_grade(self) -> None:
        """Section 5: weighted final grade (by file or by column)."""
        from pyexamgenerator.grading import FinalGradeConfig

        out = self.grad_out_var.get().strip()
        if not out:
            messagebox.showerror("Faltan datos", "Necesitas la carpeta de salida.")
            return
        mode = self.grad_final_mode_var.get()
        cap = bool(self.grad_final_cap_var.get())
        cols = self._grad_columns()

        if mode == "by_column":
            source = self.grad_final_source_var.get().strip()
            try:
                weights = self._grad_parse_weights()
            except ValueError as exc:
                messagebox.showerror("Datos no válidos", str(exc))
                return
            if not source or not weights:
                messagebox.showerror("Faltan datos", "Indica el fichero y las columnas con su peso (Columna|peso ; …).")
                return
            cfg = FinalGradeConfig(
                mode="by_column",
                source_path=source,
                weights=weights,
                output_path="calificaciones_finales_ponderadas.xlsx",
                output_dir=out,
                cap_to_10=cap,
            )
        else:
            try:
                sources = self._grad_parse_final_files()
            except ValueError as exc:
                messagebox.showerror("Datos no válidos", str(exc))
                return
            if not sources:
                messagebox.showerror("Faltan datos", "Añade al menos un examen (Fichero|peso ; …).")
                return
            cfg = FinalGradeConfig(
                mode="by_file",
                sources=sources,
                output_path="calificaciones_finales_ponderadas.xlsx",
                output_dir=out,
                cap_to_10=cap,
                id_col=cols["id_col"],
                first_name_col=cols["first_name_col"],
                last_name_col=cols["last_name_col"],
            )

        def work():
            self._grad_api(out).compute_final_grade(cfg)
            return f"Nota final calculada en:\n{out}"

        self._grad_run_async("Calculando nota final ponderada…", work)

    def run_compare_results(self, overwrite: bool) -> None:
        """Section 6: compare results against a previous version, optionally writing a merged file."""
        from pyexamgenerator.grading import ComparisonConfig

        existing = self.grad_cmp_existing_var.get().strip()
        new = self.grad_cmp_new_var.get().strip()
        out = self.grad_out_var.get().strip()
        if not (existing and new and out):
            messagebox.showerror(
                "Faltan datos", "Necesitas el fichero existente, el fichero nuevo y la carpeta de salida."
            )
            return
        value_cols = [c.strip() for c in self.grad_cmp_value_cols_var.get().split(",") if c.strip()]
        cols = self._grad_columns()
        in_place = bool(self.grad_cmp_inplace_var.get()) and overwrite
        add_new = bool(self.grad_cmp_addnew_var.get())

        if in_place and not messagebox.askyesno(
            "Confirmar sobrescritura",
            f"Se sobrescribirá el fichero existente con los valores nuevos:\n{existing}\n\n¿Continuar?",
        ):
            return

        def work():
            cfg = ComparisonConfig(
                existing_path=existing,
                new_path=new,
                value_cols=value_cols,
                overwrite=overwrite,
                add_new_rows=add_new,
                merged_in_place=in_place,
                report_output_path="comparacion_resultados.xlsx",
                merged_output_path="resultados_combinados.xlsx",
                output_dir=out,
                id_col=cols["id_col"],
                first_name_col=cols["first_name_col"],
                last_name_col=cols["last_name_col"],
            )
            result = self._grad_api(out).compare_results(cfg)
            s = result.summary
            message = (
                f"Comparación: {s['changed_cells']} celdas cambiadas en {s['changed_students']} alumno(s), "
                f"{s['added']} nuevo(s), {s['removed']} ausente(s).\nInforme en: {out}"
            )
            if overwrite:
                target = existing if in_place else os.path.join(out, "resultados_combinados.xlsx")
                message += f"\nFichero combinado: {target}"
            return message

        self._grad_run_async("Comparando resultados…", work)

    def _grad_session_fields(self) -> Dict[str, tk.Variable]:
        """Fields of the grading tab saved in a session (besides the columns), by their session key."""
        return {
            "enrollment": self.grad_enrollment_var,
            "xmls": self.grad_xmls_var,
            "images": self.grad_images_var,
            "forced_types": self.grad_forced_var,
            "answers": self.grad_answers_var,
            "theory": self.grad_theory_var,
            "attendance": self.grad_attendance_var,
            "schedule": self.grad_schedule_var,
            "justifications": self.grad_justif_var,
            "quizzes": self.grad_quizzes_var,
            "output_dir": self.grad_out_var,
            "ocr_temp_dir": self.grad_ocr_temp_dir_var,
            "schedule_sheet": self.grad_sched_sheet_var,
            "attendance_header_row": self.grad_att_header_var,
            "compare_existing": self.grad_cmp_existing_var,
            "compare_new": self.grad_cmp_new_var,
        }

    def _grad_session_inputs(self) -> dict:
        inputs = {key: var.get() for key, var in self._grad_session_fields().items()}
        inputs["append_unmatched_ocr"] = bool(self.grad_append_unmatched_var.get())
        inputs["columns"] = self._grad_columns()
        return inputs

    def save_grading_session(self) -> None:
        """Saves the current grading inputs/columns to a resumable session (.pkl + .json)."""
        from pyexamgenerator.grading import GradingSession

        path = self.grad_session_path_var.get().strip()
        if not path:
            path = filedialog.asksaveasfilename(
                title="Guardar sesión de corrección",
                defaultextension=".json",
                initialfile="sesion_correccion.json",
                filetypes=[("Sesión", "*.json *.pkl")],
            )
        if not path:
            return
        try:
            session = GradingSession(name="sesion_correccion")
            session.set_grading_inputs(**self._grad_session_inputs())
            pkl_path, json_path = session.save(path)
            self.grad_session_path_var.set(json_path)
            messagebox.showinfo("Sesión", f"Sesión guardada en:\n{pkl_path}\n{json_path}")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Error", f"No se pudo guardar la sesión: {exc}")

    def load_grading_session(self) -> None:
        """Loads a session and fills the grading inputs/columns (incl. generated exam XML paths)."""
        from pyexamgenerator.grading import GradingSession

        path = self.grad_session_path_var.get().strip()
        if not path:
            path = filedialog.askopenfilename(
                title="Cargar sesión de corrección",
                filetypes=[("Sesión JSON", "*.json"), ("Sesión pickle (solo propias)", "*.pkl"), ("Todos", "*.*")],
            )
        if not path:
            return
        try:
            session = GradingSession.load(path)
        except ValueError:
            # Only a pickle exists: unpickling can run code, so ask before trusting the file.
            if not messagebox.askyesno(
                "Sesión en formato pickle",
                "Solo se ha encontrado la sesión en formato .pkl (sin su .json).\n\n"
                "Abrir un .pkl puede ejecutar código. Continúa solo si este archivo lo has "
                "creado tú en este equipo.\n\n¿Cargarlo de todos modos?",
            ):
                return
            try:
                session = GradingSession.load(path, allow_pickle=True)
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror("Error", f"No se pudo cargar la sesión: {exc}")
                return
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Error", f"No se pudo cargar la sesión: {exc}")
            return

        gi = session.grading_inputs or {}
        for key, var in self._grad_session_fields().items():
            if gi.get(key):
                var.set(str(gi[key]))

        append_unmatched_raw = gi.get("append_unmatched_ocr", None)
        if append_unmatched_raw is not None:
            if isinstance(append_unmatched_raw, str):
                parsed_bool = append_unmatched_raw.strip().lower() in {"1", "true", "yes", "si", "sí"}
            else:
                parsed_bool = bool(append_unmatched_raw)
            self.grad_append_unmatched_var.set(parsed_bool)

        columns = gi.get("columns") or {}
        for key, (var, _default) in self._grad_column_fields().items():
            if columns.get(key):
                var.set(str(columns[key]))

        # Resume directly from generated exams: fill XML paths if the session recorded them.
        xml_paths = session.generated_xml_paths()
        if xml_paths:
            self.grad_xmls_var.set(";".join(xml_paths))

        self.grad_session_path_var.set(path)
        messagebox.showinfo("Sesión", "Sesión cargada. Rutas y columnas restauradas.")

    def run_grading(self) -> None:
        """Lanza el pipeline de corrección completo en un hilo aparte para no congelar la interfaz.

        La lógica está en :meth:`ExamCorrectionAPI.run_full_pipeline`: genera SOLO las tablas finales
        en la carpeta de salida (incidencias, cuestionarios+punto extra y calificaciones de teoría);
        los ficheros intermedios van a `_intermedios/` y se borran siempre, también tras un error.
        """
        from pyexamgenerator.grading import HAS_OCR, FullPipelineConfig

        # Every Tk variable is read here, in the main thread: work() runs in another thread.
        enrollment = [p for p in self.grad_enrollment_var.get().split(";") if p]
        xmls = [p for p in self.grad_xmls_var.get().split(";") if p]
        images = [p for p in self.grad_images_var.get().split(";") if p]
        theory = self.grad_theory_var.get().strip()
        attendance = self.grad_attendance_var.get().strip()
        schedule = self.grad_schedule_var.get().strip()
        justif = self.grad_justif_var.get().strip()
        quizzes = self.grad_quizzes_var.get().strip()
        out_dir = self.grad_out_var.get().strip()

        required = {
            "Matriculados": enrollment,
            "Plantillas XML": xmls,
            "Imágenes": images,
            "Notas de teoría": theory,
            "Asistencias": attendance,
            "Horario": schedule,
            "Justificaciones": justif,
            "Cuestionarios": quizzes,
            "Carpeta de salida": out_dir,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            messagebox.showerror("Faltan datos", "Selecciona: " + ", ".join(missing))
            return
        if not HAS_OCR:
            messagebox.showerror(
                "OCR no disponible",
                "El OCR de manuscritos requiere el extra:\n\npip install pyexamgenerator[grading]",
            )
            return

        sheet_raw = self.grad_sched_sheet_var.get().strip()
        header_raw = self.grad_att_header_var.get().strip()
        cols = self._grad_columns()
        cfg = FullPipelineConfig(
            enrollment_paths=enrollment,
            xml_paths=xmls,
            image_paths=images,
            theory_xlsx_path=theory,
            attendance_xlsx_path=attendance,
            schedule_xlsx_path=schedule,
            justifications_xlsx_path=justif,
            quizzes_xlsx_path=quizzes,
            output_dir=out_dir,
            schedule_sheet=int(sheet_raw) if sheet_raw.isdigit() else (sheet_raw or 0),
            attendance_header_row=int(header_raw) if header_raw.lstrip("-").isdigit() else 3,
            forced_type_by_image=self._grad_parse_forced(),
            temp_image_dir=self.grad_ocr_temp_dir_var.get().strip() or None,
            append_unmatched_students=bool(self.grad_append_unmatched_var.get()),
            justification_mode="extremo",
            sender_col=cols["sender_col"],
            subject_col=cols["subject_col"],
            message_col=cols["message_col"],
            first_name_col=cols["first_name_col"],
            last_name_col=cols["last_name_col"],
            id_col=cols["id_col"],
            email_col=cols["email_col"],
        )

        def work():
            def progress(message: str) -> None:
                self.root.after(0, self.update_status, f"Corrigiendo… {message}")

            api = self._grad_api(out_dir)
            api.run_full_pipeline(cfg, progress_callback=progress)

            warning_msgs: List[str] = []
            ocr_incidents = api.results.get("ocr_incidents")
            if isinstance(ocr_incidents, pd.DataFrame) and not ocr_incidents.empty:
                warning_msgs.append(
                    "Se detectaron incidencias durante el OCR "
                    f"({len(ocr_incidents)} fila(s)).\n"
                    f"Revisa: {os.path.join(out_dir, 'incidencias_identificacion_respuestas.xlsx')}"
                )
            integration_incidents_path = (api.results.get("full_pipeline_outputs") or {}).get("integration_incidents")
            warning_msgs += gui_logic.integration_warnings(
                api.results.get("ocr_integration_summary"),
                integration_incidents_path or os.path.join(out_dir, "incidencias_integracion_ocr.xlsx"),
            )
            justifications = api.results.get("justifications_summary")
            if isinstance(justifications, pd.DataFrame):
                warning_msgs += gui_logic.justification_warnings(
                    justifications.to_dict("records"),
                    "Para ver cuáles, usa «Analizar asistencia / justificaciones» (sección 2).",
                )

            msg = (
                "Corrección completada. Tablas generadas en:\n"
                + out_dir
                + "\n\n- incidencias_identificacion_respuestas.xlsx"
                "\n- cuestionarios_clase_y_punto_extra.xlsx"
                "\n- calificaciones_examen_teoria.xlsx"
            )
            if integration_incidents_path:
                msg += "\n- incidencias_integracion_ocr.xlsx"
            self._open_folder(out_dir)
            return {"info": msg, "warnings": warning_msgs}

        self._grad_run_async("Corrigiendo… (pipeline completo, puede tardar)", work, done_msg="Corrección completada.")

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
