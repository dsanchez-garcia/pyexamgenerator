# examgenerator: A tool for generating exams from PDF files using AI.
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

import tkinter as tk
import webbrowser
from tkinter import ttk, filedialog, messagebox, scrolledtext
import pandas as pd
from examgenerator.question_generator import QuestionGenerator
from examgenerator.exam_generator import ExamGenerator
from examgenerator.question_bank_manager import QuestionBankManager
from examgenerator.tooltip import ToolTip
from docx import Document
import os
import json
from ttkwidgets.frames import ScrolledFrame
import google.generativeai as genai

try:
    # Para Python 3.8+
    import importlib.metadata as importlib_metadata
except ImportError:
    # Para Python < 3.8, se usa el paquete de retrocompatibilidad
    import importlib_metadata

from typing import Optional, List, Dict, Tuple, Any


class ExamApp:
    """
    Main application for the Exam Generator Suite.

    This class builds the graphical user interface (GUI) using Tkinter,
    and orchestrates the interactions between the user and the backend modules
    (QuestionGenerator, ExamGenerator, QuestionBankManager).

    Attributes:
        root (tk.Tk): The main window of the application.
        notebook (ttk.Notebook): The widget for managing the application's tabs.
        api_key (str): The API key for using the question generator.
        question_generator (QuestionGenerator): Instance of the question generator.
        exam_generator (ExamGenerator): Instance of the exam generator.
        prompt_types (dict): Dictionary of prompt types.
        selected_prompt_type (tk.StringVar): Variable for the selected prompt type.
        custom_prompt_text (tk.StringVar): Variable for the custom prompt text.
        status_text (tk.StringVar): Variable for the status bar text.
        status_label (ttk.Label): Label for the status bar.
        excel_filepath (tk.StringVar): Variable for the Excel file path.
        subject (tk.StringVar): Variable for the subject.
        exam_name (tk.StringVar): Variable for the exam name.
        course (tk.StringVar): Variable for the course.
        num_exams (tk.StringVar): Variable for the number of exams.
        exam_names (tk.StringVar): Variable for the names of the exams.
        questions_per_topic (tk.StringVar): Variable for questions per topic (dictionary format).
        num_questions_same_topic (tk.StringVar): Variable for the number of questions per topic (same for all).
        selection_method (tk.StringVar): Variable for the question selection method.
        top_margin (tk.StringVar): Variable for the top margin.
        bottom_margin (tk.StringVar): Variable for the bottom margin.
        left_margin (tk.StringVar): Variable for the left margin.
        right_margin (tk.StringVar): Variable for the right margin.
        font_size (tk.StringVar): Variable for the font size.
        answer_sheet_instructions (tk.StringVar): Variable for the answer sheet instructions.
        penalty (tk.StringVar): Variable for the penalty.
        xml_cat_additional_text (tk.StringVar): Variable for the additional XML category text.
        export_moodle (tk.BooleanVar): Variable for exporting to Moodle.
        update_excel (tk.BooleanVar): Variable for updating the Excel file.
        num_columns_var (tk.StringVar): Variable for the number of columns in theme selection.
        selection_method_var (tk.StringVar): Variable for the theme selection method UI control.
        pdf_files_var (tk.StringVar): Variable for the PDF files.
        num_questions_var (tk.StringVar): Variable for the number of questions to generate.
        output_filename_var (tk.StringVar): Variable for the output filename.
        api_key_var (tk.StringVar): Variable for the API key.
        question_bank_manager (QuestionBankManager): Instance of the question bank manager.
        existing_bank_path (tk.StringVar): Variable for the path to an existing question bank.
        reviewed_add_path (tk.StringVar): Variable for the path to reviewed questions to be added.
    """

    def __init__(self, root: tk.Tk) -> None:
        """
        Initializes the application, setting up the main window, variables, and tabs.

        Args:
            root (tk.Tk): The main application window (tk.Tk instance).
        """
        self.root = root

        try:
            version = importlib_metadata.version('examgenerator')
        except importlib_metadata.PackageNotFoundError:
            version = "DEV"

        self.root.title(f"ExamGenerator v{version}")

        title_font = ("Helvetica", 16, "bold")
        main_title_label = ttk.Label(self.root, text=f"ExamGenerator v{version}", font=title_font)
        main_title_label.pack(pady=(10, 5), padx=10, anchor='w')

        # Lógica de carga de API Key actualizada con GEMINI_API_KEY
        initial_status = "Aplicación iniciada."
        # 1. Intentar cargar desde la variable de entorno (máxima prioridad)
        env_api_key = os.getenv('GEMINI_API_KEY') # <--- NOMBRE CORREGIDO
        if env_api_key:
            self.api_key = env_api_key
            initial_status = "Clave API cargada desde la variable de entorno GEMINI_API_KEY."
            print(initial_status)
        else:
            # 2. Si no existe, intentar cargar desde config.json (fallback)
            self.api_key = self.load_api_key()

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(expand=True, fill='both', padx=10, pady=5)

        self.question_generator = None
        self.exam_generator = ExamGenerator()
        self.prompt_types = self.load_prompt_types()
        self.selected_prompt_type = tk.StringVar()
        self.custom_prompt_text = tk.StringVar()

        self.status_text = tk.StringVar()
        self.status_label = ttk.Label(root, textvariable=self.status_text, anchor='w')
        self.status_label.pack(side='bottom', fill='x', padx=10, pady=5)
        self.update_status("Aplicación iniciada.")

        # --- Variables for the "Generate Exams" tab ---
        self.excel_filepath = tk.StringVar(value="La/ruta/del/banco/de/preguntas.xlsx")
        self.subject = tk.StringVar(value="Asignatura de Prueba")
        self.exam_name = tk.StringVar(value="Examen de Prueba")
        self.course = tk.StringVar(value="Curso 2024-2025")
        self.num_exams = tk.StringVar(value="2")
        self.exam_names = tk.StringVar(value="Tipo A,Tipo B")
        self.questions_per_topic = tk.StringVar(value="Tema 01:2,Tema 02:2")
        self.num_questions_same_topic = tk.StringVar(value="2")
        self.selection_method = tk.StringVar(value="azar")
        self.top_margin = tk.StringVar(value="1")
        self.bottom_margin = tk.StringVar(value="1")
        self.left_margin = tk.StringVar(value="0.5")
        self.right_margin = tk.StringVar(value="0.5")
        self.font_size = tk.StringVar(value="10")
        self.answer_sheet_instructions = tk.StringVar(value="Prueba GUI")
        self.penalty = tk.StringVar(value="-25")
        self.xml_cat_additional_text = tk.StringVar(value="Prueba GUI")
        self.export_moodle = tk.BooleanVar(value=False)
        self.update_excel = tk.BooleanVar(value=False)
        self.num_columns_var = tk.StringVar(value="3")
        self.selection_method_var = tk.StringVar(value="diccionario")
        self.gen_exams_output_dir_var = tk.StringVar()

        # --- Variables for the "Generate Questions" tab ---
        self.pdf_files_var = tk.StringVar()
        self.num_questions_var = tk.StringVar(value="5")
        self.output_filename_var = tk.StringVar(value="banco_prueba")
        self.api_key_var = tk.StringVar(value=self.api_key if self.api_key else "TU_CLAVE_API")
        self.gen_questions_output_dir_var = tk.StringVar()

        # self.gemini_models = {
        #     "gemini-1.5-flash": "models/gemini-1.5-flash",
        #     "gemini-1.5-pro": "models/gemini-1.5-pro",
        #     "gemini-1.0-pro": "models/gemini-1.0-pro"
        # }
        self.selected_model_var = tk.StringVar(value='')

        self.existing_bank_for_gen_path = tk.StringVar()
        self.process_by_pages_var = tk.BooleanVar(value=False)
        self.pages_per_chunk_var = tk.StringVar(value="1")
        self.max_attempts_var = tk.StringVar(value="3")
        self.print_raw_gemini_answer_var = tk.BooleanVar(value=False)
        self.use_similarity_filter_var = tk.BooleanVar(value=True)
        self.similarity_threshold_var = tk.StringVar(value="0.8")
        self.bank_in_prompt_scope_var = tk.StringVar(value="mismo_tema")
        self.prompt_example_content_var = tk.StringVar(value="solo_enunciados")

        self.question_bank_manager = QuestionBankManager()

        # --- Variables for the "Manage Bank" tab ---
        self.existing_bank_path = tk.StringVar()
        self.reviewed_add_path = tk.StringVar()
        self.add_questions_filter_var = tk.StringVar(value="todas")
        self.revised_xlsx_output_dir_var = tk.StringVar()
        self.revised_docx_path_var = tk.StringVar()
        self.new_xlsx_filename_var = tk.StringVar()
        self.duplicate_check_var = tk.StringVar(value="pregunta_unica")

        # Añadimos variables para gestionar el tooltip de la tabla de modelos
        self.tree_tooltip = None
        self.last_hovered_cell = (None, None) # Almacenará (row_id, col_id)

        self.create_question_tab()
        self.create_manage_bank_tab()
        self.create_exam_tab()

        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Ayuda", menu=help_menu)

        help_menu.add_command(label="Configurar API Key (Ayuda)...", command=self.open_api_key_help)
        help_menu.add_separator()
        help_menu.add_command(label="Acerca de...", command=self.show_about_dialog)

    def open_api_key_help(self):
        """Opens the Google AI documentation for setting up API key environment variables."""
        url = "https://ai.google.dev/gemini-api/docs/api-key?hl=es-419#set-api-env-var"
        try:
            webbrowser.open_new_tab(url)
            self.update_status(f"Abriendo enlace de ayuda en el navegador: {url}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir el enlace en el navegador.\n\nError: {e}")
            self.update_status("Error al intentar abrir el enlace de ayuda.")


    def load_prompt_types(self) -> Dict[str, str]:
        """
        Loads custom prompt types from a JSON file.

        Returns:
            Dict[str, str]: A dictionary where keys are prompt type names
                           and values are the prompt texts.
        """
        filename = "custom_prompts.json"
        custom_prompts = {}
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                try:
                    custom_prompts = json.load(f)
                except json.JSONDecodeError:
                    messagebox.showerror("Error", "Error al decodificar el archivo de prompts personalizados (custom_prompts.json).")

        default_prompts = self.load_default_prompt_types()

        # Combina ambos, dando prioridad a los personalizados si hay un conflicto de nombres.
        return {**default_prompts, **custom_prompts}

    def save_prompt_types(self) -> None:
        """
        Saves custom prompt types to a JSON file.
        """
        filename = "custom_prompt_types.json"
        custom_prompts = {k: v for k, v in self.prompt_types.items() if k not in self.load_default_prompt_types()}
        with open(filename, 'w') as f:
            json.dump(custom_prompts, f, indent=4)

    def load_default_prompt_types(self) -> Dict[str, str]:
        """
        Defines the default prompt types in a Python dictionary.

        Returns:
            Dict[str, str]: A dictionary where keys are prompt type names
                           and values are the default prompt texts.
        """
        return {
            "PRL": """
            Genera preguntas tipo test de opción múltiple enfocadas en Prevención de Riesgos Laborales (PRL), basadas en el siguiente texto, siguiendo estas instrucciones iniciales:
            \n1.  **Centrarse en leyes y reglamentos:** Las preguntas deben poder entenderse por sí mismas, haciendo referencia únicamente a leyes o reglamentos relevantes. No se puede poner: "Según el texto"
            \n2.  **Evita preguntas sobre números de artículos o códigos:** No incluyas preguntas que hagan referencia a números de artículos, códigos de leyes o reglamentos.
            """,
            "PM": "Genera preguntas tipo test de opción múltiple enfocadas en Gestión de Proyectos."
        }

    def save_prompt_types(self) -> None:
        """
        Saves custom prompt types to a JSON file.
        """
        filename = "custom_prompts.json"
        # Filtra para guardar solo los prompts que no son los predeterminados.
        custom_prompts = {k: v for k, v in self.prompt_types.items() if k not in self.load_default_prompt_types()}
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(custom_prompts, f, indent=4, ensure_ascii=False)

    def add_edit_prompt_type(self, existing_type: Optional[str] = None) -> None:
        """
        Opens a Toplevel window to add a new prompt type or edit an existing one.
        """
        add_window = tk.Toplevel(self.root)
        title = "Editar Tipo de Prompt" if existing_type else "Añadir Nuevo Tipo de Prompt"
        add_window.title(title)

        ttk.Label(add_window, text="Nombre del Tipo (ej. 'Historia'):").grid(row=0, column=0, padx=10, pady=5, sticky='w')
        type_entry = ttk.Entry(add_window, width=40)
        type_entry.grid(row=0, column=1, padx=10, pady=5, sticky='ew')

        ttk.Label(add_window, text="Texto del Prompt:").grid(row=1, column=0, padx=10, pady=5, sticky='nw')
        prompt_text_area = scrolledtext.ScrolledText(add_window, width=60, height=10, wrap=tk.WORD)
        prompt_text_area.grid(row=1, column=1, padx=10, pady=5, sticky='nsew')

        if existing_type:
            type_entry.insert(0, existing_type)
            if existing_type in self.load_default_prompt_types():
                type_entry.config(state='disabled')  # No se puede cambiar el nombre a los predeterminados
            prompt_text_area.insert("1.0", self.prompt_types.get(existing_type, ""))

        def save_action():
            new_type = type_entry.get().strip()
            new_prompt = prompt_text_area.get("1.0", tk.END).strip()

            if not new_type or not new_prompt:
                messagebox.showerror("Error", "El nombre del tipo y el texto del prompt no pueden estar vacíos.", parent=add_window)
                return

            if not existing_type and new_type in self.prompt_types:
                if not messagebox.askyesno("Sobrescribir", f"El tipo '{new_type}' ya existe. ¿Desea sobrescribirlo?", parent=add_window):
                    return

            self.prompt_types[new_type] = new_prompt
            self.save_prompt_types()
            self.update_prompt_type_options()
            self.selected_prompt_type.set(new_type)
            self.update_custom_prompt_display()
            add_window.destroy()

        save_button = ttk.Button(add_window, text="Guardar", command=save_action)
        save_button.grid(row=2, column=1, padx=10, pady=10, sticky='e')

        add_window.columnconfigure(1, weight=1)
        add_window.rowconfigure(1, weight=1)
        add_window.transient(self.root)
        add_window.grab_set()

    def delete_prompt_type(self) -> None:
        """
        Deletes the currently selected custom prompt type.
        """
        selected_type = self.selected_prompt_type.get()
        if not selected_type:
            messagebox.showwarning("Sin selección", "Por favor, seleccione un tipo de prompt para eliminar.")
            return

        if selected_type in self.load_default_prompt_types():
            messagebox.showerror("Error", "No se pueden eliminar los tipos de prompt predeterminados (PRL, PM).")
            return

        if messagebox.askyesno("Confirmar Eliminación", f"¿Está seguro de que desea eliminar permanentemente el tipo de prompt '{selected_type}'?"):
            del self.prompt_types[selected_type]
            self.save_prompt_types()
            self.update_prompt_type_options()
            messagebox.showinfo("Eliminado", f"El tipo de prompt '{selected_type}' ha sido eliminado.")

    def update_prompt_type_options(self) -> None:
        """
        Updates the options in the prompt type dropdown menu and selects the first one.
        """
        prompt_type_names = sorted(list(self.prompt_types.keys()))
        current_selection = self.selected_prompt_type.get()

        if hasattr(self, 'prompt_type_combo'):
            self.prompt_type_combo['values'] = prompt_type_names

        if prompt_type_names:
            if current_selection in prompt_type_names:
                self.selected_prompt_type.set(current_selection)
            else:
                self.selected_prompt_type.set(prompt_type_names[0])
            self.update_custom_prompt_display()
        else:
            self.selected_prompt_type.set("")
            self.update_custom_prompt_display()

    def add_edit_prompt_type(self, existing_type: Optional[str] = None,
                             existing_prompt: Optional[str] = None) -> None:
        """
        Adds or edits a prompt type via a new Toplevel window.

        Args:
            existing_type (Optional[str], optional): The existing prompt type (for editing). Defaults to None.
            existing_prompt (Optional[str], optional): The existing prompt text (for editing). Defaults to None.
        """
        add_window = tk.Toplevel(self.root)
        add_window.title("Añadir/Editar Tipo de Prompt")

        ttk.Label(add_window, text="Tipo de Prompt:").grid(row=0, column=0, padx=5, pady=5, sticky='w')
        type_entry = ttk.Entry(add_window, width=30)
        type_entry.grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        if existing_type:
            type_entry.insert(0, existing_type)
            type_entry.config(state='disabled')

        ttk.Label(add_window, text="Prompt:").grid(row=1, column=0, padx=5, pady=5, sticky='nw')
        prompt_text_area = scrolledtext.ScrolledText(add_window, width=40, height=5)
        prompt_text_area.grid(row=1, column=1, padx=5, pady=5, sticky='ew')
        if existing_prompt:
            prompt_text_area.insert("1.0", existing_prompt)

        def save_prompt_type():
            new_type = type_entry.get().strip()
            new_prompt = prompt_text_area.get("1.0", tk.END).strip()
            if new_type and new_prompt:
                if existing_type:
                    self.prompt_types[existing_type] = new_prompt
                else:
                    if new_type in self.prompt_types:
                        if messagebox.askyesno("Advertencia", f"El tipo '{new_type}' ya existe. ¿Desea sobrescribirlo?"):
                            self.prompt_types[new_type] = new_prompt
                        else:
                            return
                    else:
                        self.prompt_types[new_type] = new_prompt
                self.update_prompt_type_options()
                self.save_prompt_types()  # Save after adding/editing.
                add_window.destroy()
            else:
                messagebox.showerror("Error", "Por favor, introduce un tipo y un prompt.")

        ttk.Button(add_window, text="Guardar", command=save_prompt_type).grid(row=2, column=0, columnspan=2, pady=10)
        add_window.columnconfigure(1, weight=1)

    def delete_prompt_type(self) -> None:
        """
        Deletes the selected prompt type, preventing deletion of default types.
        """
        selected_type = self.prompt_type_combo.get()
        if selected_type in self.prompt_types and selected_type not in ["PRL", "PM"]:
            if messagebox.askyesno("Confirmar", f"¿Seguro que desea eliminar el tipo de prompt '{selected_type}'?"):
                del self.prompt_types[selected_type]
                self.update_prompt_type_options()
                self.save_prompt_types()  # Save after deleting.
        elif selected_type in ["PRL", "PM"]:
            messagebox.showerror("Error", "No se pueden eliminar los tipos de prompt predeterminados.")
        else:
            messagebox.showinfo("Información", "Por favor, seleccione un tipo de prompt para eliminar.")

    def update_prompt_type_options(self) -> None:
        """
        Updates the options in the prompt type dropdown menu.
        """
        prompt_type_names = list(self.prompt_types.keys())
        self.prompt_type_combo['values'] = prompt_type_names
        if prompt_type_names:
            self.prompt_type_combo.set(prompt_type_names[0])
            self.update_custom_prompt_display()

    def update_custom_prompt_display(self, event: Optional[tk.Event] = None) -> None:
        """
        Updates the custom prompt text in the GUI.

        This method displays the text of the selected prompt type in the
        corresponding text area. If no prompt type is selected or the
        selected type does not exist, the text area is cleared.

        Args:
            event (Optional[tk.Event]): The event that triggered this method call. Defaults to None.
        """
        selected_type = self.prompt_type_combo.get()
        if selected_type in self.prompt_types:
            self.custom_prompt_text.set(self.prompt_types[selected_type])
        else:
            self.custom_prompt_text.set("")
        if hasattr(self, 'prompt_text_display'):
            self.prompt_text_display.config(state=tk.NORMAL)
            self.prompt_text_display.delete("1.0", tk.END)
            self.prompt_text_display.insert(tk.END, self.custom_prompt_text.get())
            self.prompt_text_display.config(state=tk.DISABLED)

    def update_status(self, message: str) -> None:
        """
        Updates the text of the status bar.

        Args:
            message (str): The text to display in the status bar.
        """
        self.status_text.set(message)

    def toggle_pages_per_chunk_entry(self):
        """
        Enables or disables the 'pages per chunk' entry based on the checkbox state.
        """
        if self.process_by_pages_var.get():
            self.pages_per_chunk_entry.config(state='normal')
        else:
            self.pages_per_chunk_entry.config(state='disabled')

    def create_question_tab(self) -> None:
        """
        Creates the 'Generate Questions' tab with all its widgets.
        """
        question_tab = ttk.Frame(self.notebook)
        self.notebook.add(question_tab, text='Generar Preguntas')

        # Canvas to enable scrolling
        canvas_question = tk.Canvas(question_tab)
        scrollbar_question = ttk.Scrollbar(question_tab, orient="vertical", command=canvas_question.yview)
        canvas_question.configure(yscrollcommand=scrollbar_question.set)
        scrollbar_question.pack(side="right", fill="y")
        canvas_question.pack(side="left", fill="both", expand=True)
        canvas_question.bind("<MouseWheel>", lambda event: canvas_question.yview_scroll(int(-1 * (event.delta / 120)), "units"))
        canvas_question.bind("<Button-4>", lambda event: canvas_question.yview_scroll(-1, "units"))
        canvas_question.bind("<Button-5>", lambda event: canvas_question.yview_scroll(1, "units"))

        inner_frame_question = ttk.Frame(canvas_question)
        inner_frame_question.bind("<Configure>", lambda e: canvas_question.configure(scrollregion=canvas_question.bbox("all")))
        canvas_question.create_window((0, 0), window=inner_frame_question, anchor="nw")
        inner_frame_question.bind("<MouseWheel>", lambda event: canvas_question.yview_scroll(int(-1 * (event.delta / 120)), "units"))
        inner_frame_question.bind("<Button-4>", lambda event: canvas_question.yview_scroll(-1, "units"))
        inner_frame_question.bind("<Button-5>", lambda event: canvas_question.yview_scroll(1, "units"))

        # --- Prompts and PDF section ---
        prompt_type_frame = ttk.LabelFrame(inner_frame_question, text="Seleccionar/Editar Tipo de Prompt")
        prompt_type_frame.pack(padx=10, pady=10, fill='x')

        prompt_type_label = ttk.Label(prompt_type_frame, text="Tipo de Prompt:")
        prompt_type_label.grid(row=0, column=0, padx=5, pady=5, sticky='w')
        ToolTip(prompt_type_label, "Seleccione el prompt base para la generación de preguntas.")
        prompt_type_names = list(self.prompt_types.keys())
        self.prompt_type_combo = ttk.Combobox(prompt_type_frame, textvariable=self.selected_prompt_type, values=prompt_type_names, state='readonly')
        self.prompt_type_combo.grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        self.prompt_type_combo.bind("<<ComboboxSelected>>", self.update_custom_prompt_display)
        if prompt_type_names:
            self.prompt_type_combo.set(prompt_type_names[0])
        ToolTip(self.prompt_type_combo, "Lista de tipos de prompts disponibles.")

        # CAMBIO: Frame para los botones de gestión de prompts
        prompt_buttons_frame = ttk.Frame(prompt_type_frame)
        prompt_buttons_frame.grid(row=0, column=2, padx=5, pady=5)

        add_prompt_button = ttk.Button(prompt_buttons_frame, text="Añadir", command=self.add_edit_prompt_type)
        add_prompt_button.pack(side='left', padx=2)
        ToolTip(add_prompt_button, "Añadir un nuevo tipo de prompt personalizado.")

        edit_prompt_button = ttk.Button(prompt_buttons_frame, text="Editar", command=lambda: self.add_edit_prompt_type(existing_type=self.selected_prompt_type.get()))
        edit_prompt_button.pack(side='left', padx=2)
        ToolTip(edit_prompt_button, "Editar el tipo de prompt seleccionado actualmente.")

        delete_prompt_button = ttk.Button(prompt_buttons_frame, text="Eliminar", command=self.delete_prompt_type)
        delete_prompt_button.pack(side='left', padx=2)
        ToolTip(delete_prompt_button, "Eliminar el tipo de prompt seleccionado (no se pueden eliminar los predeterminados).")

        prompt_type_frame.columnconfigure(1, weight=1)

        selected_prompt_frame = ttk.LabelFrame(inner_frame_question, text="Prompt Seleccionado")
        selected_prompt_frame.pack(padx=10, pady=10, fill='both', expand=True)
        self.prompt_text_display = scrolledtext.ScrolledText(selected_prompt_frame, state=tk.DISABLED)
        self.prompt_text_display.pack(padx=5, pady=5, fill='both', expand=True)
        self.update_custom_prompt_display()
        ToolTip(self.prompt_text_display, "Texto del prompt seleccionado. No editable directamente aquí.")

        pdf_frame = ttk.LabelFrame(inner_frame_question, text="Seleccionar Archivos PDF")
        pdf_frame.pack(padx=10, pady=10, fill='x')
        pdf_label = ttk.Label(pdf_frame, text="Archivos PDF:")
        pdf_label.grid(row=0, column=0, padx=5, pady=5, sticky='w')
        ToolTip(pdf_label, "Seleccione los archivos PDF desde los cuales se generarán las preguntas.")
        self.pdf_entry = ttk.Entry(pdf_frame, width=50, textvariable=self.pdf_files_var)
        self.pdf_entry.grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        ToolTip(self.pdf_entry, "Rutas de los archivos PDF seleccionados (separados por comas).")
        select_pdf_button = ttk.Button(pdf_frame, text="Seleccionar PDFs", command=self.select_pdf_files)
        select_pdf_button.grid(row=0, column=2, padx=5, pady=5)
        ToolTip(select_pdf_button, "Abre un diálogo para seleccionar uno o más archivos PDF.")
        pdf_frame.columnconfigure(1, weight=1)

        # --- Generation configuration section ---
        config_frame = ttk.LabelFrame(inner_frame_question, text="Configuración de Generación")
        config_frame.pack(padx=10, pady=10, fill='x', expand=True)

        # Row 0: Target questions per PDF/chunk
        num_questions_label = ttk.Label(config_frame, text="Preguntas objetivo por PDF/fragmento:")
        num_questions_label.grid(row=0, column=0, padx=5, pady=5, sticky='w')
        ToolTip(num_questions_label, "El número de preguntas que la aplicación intentará generar para cada PDF o fragmento.")
        num_questions_entry = ttk.Entry(config_frame, width=10, textvariable=self.num_questions_var)
        num_questions_entry.grid(row=0, column=1, padx=5, pady=5, sticky='w')
        ToolTip(num_questions_entry, "Introduzca el número deseado de preguntas.")

        # Row 1: Output Filename
        output_filename_label = ttk.Label(config_frame, text="Nombre Archivo Salida:")
        output_filename_label.grid(row=1, column=0, padx=5, pady=5, sticky='w')
        ToolTip(output_filename_label, "Nombre base para los archivos de salida Excel y DOCX.")
        output_filename_entry = ttk.Entry(config_frame, width=30, textvariable=self.output_filename_var)
        output_filename_entry.grid(row=1, column=1, columnspan=2, padx=5, pady=5, sticky='ew')
        ToolTip(output_filename_entry, "Introduzca el nombre base para los archivos generados.")

        # Row 2: Processing Mode
        processing_frame = ttk.LabelFrame(config_frame, text="Modo de Procesamiento")
        processing_frame.grid(row=2, column=0, columnspan=3, padx=5, pady=5, sticky='ew')
        process_by_pages_check = ttk.Checkbutton(processing_frame, text="Procesar PDF por fragmentos", variable=self.process_by_pages_var, command=self.toggle_pages_per_chunk_entry)
        process_by_pages_check.grid(row=0, column=0, padx=5, pady=5, sticky='w')
        ToolTip(process_by_pages_check, "Si se marca, el PDF se dividirá en fragmentos más pequeños para la generación. Útil para documentos grandes.")
        pages_per_chunk_label = ttk.Label(processing_frame, text="Páginas por fragmento:")
        pages_per_chunk_label.grid(row=0, column=1, padx=5, pady=5, sticky='w')
        ToolTip(pages_per_chunk_label, "Número de páginas a incluir en cada fragmento de procesamiento.")
        self.pages_per_chunk_entry = ttk.Entry(processing_frame, width=5, textvariable=self.pages_per_chunk_var, state='disabled')
        self.pages_per_chunk_entry.grid(row=0, column=2, padx=5, pady=5, sticky='w')
        ToolTip(self.pages_per_chunk_entry, "Introduzca el número de páginas para cada fragmento.")

        # Row 3: Max attempts per chunk
        max_attempts_label = ttk.Label(config_frame, text="Máx. intentos por fragmento:")
        max_attempts_label.grid(row=3, column=0, padx=5, pady=5, sticky='w')
        ToolTip(max_attempts_label, "Número máximo de veces que se llamará a la API para un único fragmento si no se alcanza el objetivo de preguntas.")
        max_attempts_entry = ttk.Entry(config_frame, width=5, textvariable=self.max_attempts_var)
        max_attempts_entry.grid(row=3, column=1, padx=5, pady=5, sticky='w')
        ToolTip(max_attempts_entry, "Número máximo de intentos de generación por fragmento si no se alcanza el objetivo (Recomendado: 3).\nAfecta al uso de la API de Gemini (más intentos = más uso y posible límite diario).")

        # Row 4: Duplicate Filter
        similarity_filter_frame = ttk.LabelFrame(config_frame, text="Filtro de Duplicados")
        similarity_filter_frame.grid(row=4, column=0, columnspan=3, padx=5, pady=5, sticky='ew')
        ToolTip(similarity_filter_frame, "Compara cada pregunta generada con un banco existente y descarta las que sean muy parecidas (basado solo en el enunciado).")

        existing_bank_label = ttk.Label(similarity_filter_frame, text="Banco Existente a Consultar:")
        existing_bank_label.grid(row=0, column=0, padx=5, pady=5, sticky='w')
        ToolTip(existing_bank_label, "Seleccione un archivo Excel con preguntas existentes para evitar generar duplicados.")
        existing_bank_entry = ttk.Entry(similarity_filter_frame, textvariable=self.existing_bank_for_gen_path)
        existing_bank_entry.grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        ToolTip(existing_bank_entry, "Ruta al archivo del banco de preguntas existente.")
        select_existing_button = ttk.Button(similarity_filter_frame, text="Seleccionar", command=self.select_existing_bank_for_gen_file)
        select_existing_button.grid(row=0, column=2, padx=5, pady=5)
        ToolTip(select_existing_button, "Abre un diálogo para seleccionar el archivo del banco de preguntas.")
        similarity_filter_frame.columnconfigure(1, weight=1)

        use_similarity_check = ttk.Checkbutton(similarity_filter_frame, text="Activar filtro de similitud", variable=self.use_similarity_filter_var)
        use_similarity_check.grid(row=1, column=0, padx=5, pady=2, sticky='w')
        ToolTip(use_similarity_check, "Si se marca, las preguntas generadas se compararán con el banco existente y se descartarán si son demasiado similares.")

        threshold_label = ttk.Label(similarity_filter_frame, text="Umbral de similitud:")
        threshold_label.grid(row=1, column=1, padx=5, pady=2, sticky='w')
        ToolTip(threshold_label, "Valor entre 0.0 y 1.0. Un valor más alto significa que las preguntas deben ser más idénticas para ser descartadas (0.8 es un buen punto de partida).")

        threshold_spinbox = ttk.Spinbox(similarity_filter_frame, from_=0.0, to=1.0, increment=0.05, width=6, textvariable=self.similarity_threshold_var)
        threshold_spinbox.grid(row=1, column=2, padx=5, pady=2, sticky='w')
        ToolTip(threshold_spinbox, "Ajuste el umbral de similitud. 1.0 significa una coincidencia exacta.")

        # Row 5: Bank Inclusion in Prompt
        prompt_inclusion_frame = ttk.LabelFrame(config_frame, text="Inclusión de Banco en Prompt (si se selecciona banco)")
        prompt_inclusion_frame.grid(row=5, column=0, columnspan=3, padx=5, pady=5, sticky='ew')
        ToolTip(prompt_inclusion_frame, "Define qué preguntas del banco y qué contenido de ellas se incluye en el prompt para guiar la generación.")

        scope_frame = ttk.LabelFrame(prompt_inclusion_frame, text="Alcance de Preguntas de para evitar similares en Prompt")
        scope_frame.pack(fill='x', padx=5, pady=(5, 0))

        same_topic_radio = ttk.Radiobutton(scope_frame,
                                           text="Usar preguntas del mismo tema",
                                           variable=self.bank_in_prompt_scope_var,
                                           value="mismo_tema")
        same_topic_radio.pack(anchor='w', padx=10, pady=2)
        ToolTip(same_topic_radio, "Se usarán como ejemplo preguntas del banco que coincidan con el tema del PDF actual.")

        all_topics_radio = ttk.Radiobutton(scope_frame,
                                           text="Usar todas las preguntas del banco",
                                           variable=self.bank_in_prompt_scope_var,
                                           value="todos_los_temas")
        all_topics_radio.pack(anchor='w', padx=10, pady=2)
        ToolTip(all_topics_radio, "Se usarán como ejemplo todas las preguntas del banco, independientemente del tema.")

        content_frame = ttk.LabelFrame(prompt_inclusion_frame, text="Contenido de Preguntas de para evitar similares en Prompt")
        content_frame.pack(fill='x', padx=5, pady=5)

        enunciados_radio = ttk.Radiobutton(content_frame,
                                           text="Incluir solo enunciados (recomendado)",
                                           variable=self.prompt_example_content_var,
                                           value="solo_enunciados")
        enunciados_radio.pack(anchor='w', padx=10, pady=2)
        ToolTip(enunciados_radio, "En el prompt, las preguntas de ejemplo solo mostrarán su enunciado.")

        enunciados_resp_radio = ttk.Radiobutton(content_frame,
                                                text="Incluir enunciados y respuestas",
                                                variable=self.prompt_example_content_var,
                                                value="enunciados_y_respuestas")
        enunciados_resp_radio.pack(anchor='w', padx=10, pady=2)
        ToolTip(enunciados_resp_radio, "En el prompt, las preguntas de ejemplo mostrarán su enunciado y sus opciones de respuesta.")

        # Row 6: Model and API Key - Ahora con una tabla
        model_api_frame = ttk.LabelFrame(config_frame, text="Modelo y Clave API")
        model_api_frame.grid(row=6, column=0, columnspan=3, padx=5, pady=5, sticky='ew')

        # API Key sigue igual
        api_key_label = ttk.Label(model_api_frame, text="Clave API de Gemini:")
        api_key_label.grid(row=0, column=0, padx=5, pady=5, sticky='w')
        ToolTip(api_key_label, "Su clave personal de API para Google Gemini.")
        self.api_key_entry = ttk.Entry(model_api_frame, width=40, textvariable=self.api_key_var, show="*")
        self.api_key_entry.grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        ToolTip(self.api_key_entry, "Introduzca aquí su clave de API.")

        api_buttons_frame = ttk.Frame(model_api_frame)
        api_buttons_frame.grid(row=0, column=2, padx=5, pady=5, sticky='w')

        save_api_key_button = ttk.Button(api_buttons_frame, text="Guardar Clave", command=self.save_current_api_key)
        save_api_key_button.pack(side='left', padx=2)
        ToolTip(save_api_key_button, text="Guarda la clave de API actual en la configuración.")

        load_models_button = ttk.Button(api_buttons_frame, text="Cargar Modelos", command=self.populate_models_table)
        load_models_button.pack(side='left', padx=2)
        ToolTip(load_models_button, text="Usa la clave API para obtener la lista de modelos disponibles.")

        # Nueva tabla para los modelos
        models_table_frame = ttk.Frame(model_api_frame)
        models_table_frame.grid(row=1, column=0, columnspan=3, padx=5, pady=5, sticky='nsew')

        # Ampliamos las columnas a mostrar
        cols = ('name', 'display_name', 'version', 'input_tokens', 'output_tokens', 'methods', 'description')
        self.models_tree = ttk.Treeview(models_table_frame, columns=cols, show='headings', height=6)

        # Definir encabezados
        self.models_tree.heading('name', text='Nombre Técnico')
        self.models_tree.heading('display_name', text='Nombre')
        self.models_tree.heading('version', text='Versión')
        self.models_tree.heading('input_tokens', text='Tokens Entrada')
        self.models_tree.heading('output_tokens', text='Tokens Salida')
        self.models_tree.heading('methods', text='Métodos Soportados')
        self.models_tree.heading('description', text='Descripción')

        # Definir anchos y alineación de columna
        self.models_tree.column('name', width=180, stretch=tk.NO)
        self.models_tree.column('display_name', width=150, stretch=tk.NO)
        self.models_tree.column('version', width=60, stretch=tk.NO, anchor='center')
        self.models_tree.column('input_tokens', width=100, stretch=tk.NO, anchor='e')  # 'e' para alinear a la derecha (este)
        self.models_tree.column('output_tokens', width=100, stretch=tk.NO, anchor='e')
        self.models_tree.column('methods', width=200)
        self.models_tree.column('description', width=400)

        # Añadir scrollbars
        vsb = ttk.Scrollbar(models_table_frame, orient="vertical", command=self.models_tree.yview)
        hsb = ttk.Scrollbar(models_table_frame, orient="horizontal", command=self.models_tree.xview)
        self.models_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.models_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')

        models_table_frame.grid_rowconfigure(0, weight=1)
        models_table_frame.grid_columnconfigure(0, weight=1)

        # Vincular el evento de selección
        self.models_tree.bind('<<TreeviewSelect>>', self.on_model_select)
        # Vinculamos los eventos de movimiento y salida del ratón para el tooltip
        self.models_tree.bind('<Motion>', self.on_treeview_motion)
        self.models_tree.bind('<Leave>', self.hide_tree_tooltip)

        model_api_frame.columnconfigure(1, weight=1)
        model_api_frame.rowconfigure(1, weight=1)

        # Row 7: Checkbox to print raw response
        debug_options_frame = ttk.Frame(config_frame)
        debug_options_frame.grid(row=7, column=0, columnspan=3, padx=5, pady=5, sticky='ew')

        print_raw_check = ttk.Checkbutton(debug_options_frame, text="Imprimir respuesta cruda de Gemini (depuración)", variable=self.print_raw_gemini_answer_var)
        print_raw_check.pack(anchor='w', padx=5)
        ToolTip(print_raw_check, "Si se marca, la respuesta completa de la API de Gemini se imprimirá en la consola. Útil para depuración.")

        # Row 8: Output Directory
        output_dir_frame = ttk.LabelFrame(config_frame, text="Directorio de Salida")
        output_dir_frame.grid(row=8, column=0, columnspan=3, padx=5, pady=5, sticky='ew')
        ToolTip(output_dir_frame, "Carpeta donde se guardarán los archivos generados. Si se deja en blanco, se usará la carpeta actual.")

        output_dir_entry = ttk.Entry(output_dir_frame, textvariable=self.gen_questions_output_dir_var)
        output_dir_entry.pack(side='left', fill='x', expand=True, padx=5, pady=5)
        ToolTip(output_dir_entry, "Ruta al directorio de salida.")

        output_dir_button = ttk.Button(output_dir_frame, text="Seleccionar...", command=self.select_gen_questions_output_dir)
        output_dir_button.pack(side='left', padx=5, pady=5)
        ToolTip(output_dir_button, "Abrir diálogo para seleccionar el directorio de salida.")

        # Row 9: Generate Button
        generate_button = ttk.Button(config_frame, text="Generar Preguntas", command=self.generate_questions)
        generate_button.grid(row=9, column=0, columnspan=3, pady=10)
        ToolTip(generate_button, "Iniciar el proceso de generación de preguntas con la configuración actual.")

        config_frame.columnconfigure(1, weight=1)
        inner_frame_question.columnconfigure(0, weight=1)

    def populate_models_table(self):
        """
        Fetches available Gemini models using the provided API key and populates the Treeview table.
        """
        api_key = self.api_key_var.get()
        if not api_key or api_key == "TU_CLAVE_API":
            messagebox.showerror("Error", "Por favor, introduce una clave API de Gemini válida antes de cargar los modelos.")
            return

        self.update_status("Cargando lista de modelos...")
        self.root.update_idletasks()

        # Limpiar la tabla antes de llenarla
        for i in self.models_tree.get_children():
            self.models_tree.delete(i)

        try:
            genai.configure(api_key=api_key)

            # Obtenemos todos los modelos y filtramos por los que pueden generar contenido
            available_models = [
                m for m in genai.list_models()
                if 'generateContent' in m.supported_generation_methods
            ]

            if not available_models:
                messagebox.showwarning("Sin Modelos", "No se encontraron modelos compatibles con la generación de contenido.")
                self.update_status("No se encontraron modelos compatibles.")
                return

            # Insertamos todas las nuevas columnas de datos
            for model in available_models:
                # Convertimos la lista de métodos a una cadena de texto legible
                methods_str = ', '.join(model.supported_generation_methods)

                self.models_tree.insert("", "end", values=(
                    model.name,
                    model.display_name,
                    model.version,
                    model.input_token_limit,
                    model.output_token_limit,
                    methods_str,
                    model.description.replace('\n', ' ')  # Evitar saltos de línea en la descripción
                ))

            self.update_status(f"Se cargaron {len(available_models)} modelos. Por favor, seleccione uno de la tabla.")

        except Exception as e:
            messagebox.showerror("Error de API", f"No se pudo obtener la lista de modelos. Verifica tu clave API y conexión a internet.\n\nError: {e}")
            self.update_status("Error al cargar modelos.")

    # Nueva función para manejar la selección en la tabla
    def on_model_select(self, event=None):
        """
        Handles the selection of a model in the Treeview table.
        Updates the selected_model_var with the technical name of the chosen model.
        """
        selected_items = self.models_tree.selection()
        if selected_items:
            # Obtenemos el primer item seleccionado
            selected_item = selected_items[0]
            # Obtenemos los valores de la fila seleccionada
            item_values = self.models_tree.item(selected_item, 'values')
            # El primer valor es el nombre técnico (ej. 'models/gemini-1.5-pro')
            technical_name = item_values[0]

            self.selected_model_var.set(technical_name)
            self.update_status(f"Modelo seleccionado: {technical_name}")

    def on_treeview_motion(self, event):
        """
        Shows a tooltip with the full cell text if the mouse hovers over a cell
        where the content is wider than the column.
        """
        # Identificar la fila y columna bajo el cursor
        row_id = self.models_tree.identify_row(event.y)
        col_id = self.models_tree.identify_column(event.x)

        # Si no estamos sobre una celda válida, ocultar tooltip y salir
        if not row_id or not col_id:
            self.hide_tree_tooltip()
            return

        # Evitar parpadeo si seguimos en la misma celda
        if (row_id, col_id) == self.last_hovered_cell:
            return

        # Si nos movemos a una nueva celda, ocultar el tooltip anterior
        self.hide_tree_tooltip()
        self.last_hovered_cell = (row_id, col_id)

        try:
            # Convertir el identificador de columna (ej. '#3') a un índice numérico (ej. 2)
            col_index = int(col_id.replace('#', '')) - 1
            if col_index < 0: return

            # Obtener el texto completo de la celda
            cell_text = self.models_tree.item(row_id, 'values')[col_index]

            # Comprobar si el texto es más ancho que la columna
            col_width = self.models_tree.column(col_id, 'width')

            ### CAMBIO ###
            # Usamos la fuente por defecto de la aplicación para medir el ancho del texto
            from tkinter import font
            f = font.Font()  # Obtiene la fuente por defecto de la aplicación
            text_width = f.measure(str(cell_text))

            # Solo mostrar el tooltip si el texto es más largo que la columna
            if text_width > col_width:
                # Crear la ventana del tooltip
                self.tree_tooltip = tw = tk.Toplevel(self.root)
                tw.wm_overrideredirect(True)  # Sin bordes ni barra de título

                # Posicionar el tooltip cerca del cursor
                x = self.root.winfo_pointerx() + 15
                y = self.root.winfo_pointery() + 10
                tw.wm_geometry(f"+{x}+{y}")

                # Añadir una etiqueta con el texto completo
                label = ttk.Label(tw, text=cell_text, justify='left',
                                  background="#FFFFE0", relief='solid', borderwidth=1,
                                  wraplength=500)  # wraplength para descripciones muy largas
                label.pack(ipadx=2, ipady=2)

        except (ValueError, IndexError):
            # Ocurre si el cursor está sobre un área vacía o hay un error al obtener datos
            pass

    def hide_tree_tooltip(self, event=None):
        """Hides the treeview tooltip."""
        if self.tree_tooltip:
            self.tree_tooltip.destroy()
            self.tree_tooltip = None
        # Reseteamos la última celda para que el tooltip se vuelva a mostrar si volvemos a entrar
        self.last_hovered_cell = (None, None)

    def load_api_key(self) -> Optional[str]:
        """
        Loads the API key from a configuration file.

        Returns:
            Optional[str]: The API key if found, otherwise None.
        """
        try:
            with open('config.json', 'r') as f:
                config = json.load(f)
                return config.get('api_key')
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def save_api_key(self, api_key: str) -> None:
        """
        Saves the API key to a configuration file.

        Args:
            api_key (str): The API key to save.
        """
        with open('config.json', 'w') as f:
            json.dump({'api_key': api_key}, f)
        messagebox.showinfo("Info", "API key guardada.")

    def save_current_api_key(self) -> None:
        """
        Saves the API key currently entered in the GUI.

        This method gets the API key from the GUI variable,
        saves it using the `save_api_key` method, and updates the
        question generator instance (`self.question_generator`) with the new API key.
        It also shows informational or error messages to the user via messagebox.
        """
        key_to_save = self.api_key_var.get()
        if key_to_save:
            self.save_api_key(key_to_save)
            self.api_key = key_to_save  # Update the API key in the instance.
            try:
                self.question_generator = QuestionGenerator(self.api_key)  # Re-initialize the model with the new key.
            except Exception as e:
                messagebox.showerror("Error", f"Error al inicializar el generador de preguntas: {e}")
            messagebox.showinfo("Info", "La API key ha sido actualizada y guardada.")
        else:
            messagebox.showerror("Error", "Por favor, introduce la API key.")

    def select_pdf_files(self) -> None:
        """
        Opens a dialog for the user to select one or more PDF files.
        The paths of the selected files are inserted into the corresponding entry widget.
        """
        file_paths = filedialog.askopenfilenames(
            title="Seleccionar archivos PDF",
            filetypes=(("Archivos PDF", "*.pdf"), ("Todos los archivos", "*.*"))
        )
        self.pdf_entry.insert(tk.END, ",".join(file_paths))

    def select_existing_bank_for_gen_file(self) -> None:
        """
        Opens a dialog for the user to select an existing Excel file
        to use as a question bank when generating new questions (optional).
        The path of the selected file is saved in the `self.existing_bank_for_gen_path` variable.
        """
        filepath = filedialog.askopenfilename(
            title="Seleccionar Banco de Preguntas Existente (Opcional)",
            filetypes=[("Archivos Excel", "*.xlsx;*.xls")]
        )
        if filepath:
            self.existing_bank_for_gen_path.set(filepath)

    def generate_questions(self) -> None:
        """
        Gathers all parameters from the GUI and triggers the question generation process.
        This function acts as a bridge between the user interface and the backend logic.
        """
        api_key = self.api_key_var.get()
        pdf_paths_str = self.pdf_files_var.get()
        pdf_paths = [path.strip() for path in pdf_paths_str.split(',') if path.strip()]
        selected_prompt_type = self.selected_prompt_type.get()
        custom_prompt_text_to_use = self.custom_prompt_text.get()

        try:
            # This is the TARGET number of questions per chunk.
            num_questions_target_per_chunk = int(self.num_questions_var.get())
            if num_questions_target_per_chunk <= 0:
                messagebox.showerror("Error", "El número de preguntas objetivo por PDF/fragmento debe ser positivo.")
                return
        except ValueError:
            messagebox.showerror("Error", "El número de preguntas objetivo por PDF/fragmento debe ser un entero.")
            return

        # Get and validate the maximum number of attempts.
        try:
            max_attempts_value = int(self.max_attempts_var.get())
            if max_attempts_value < 1:
                messagebox.showerror("Error", "El número máximo de intentos por fragmento debe ser al menos 1.")
                return
        except ValueError:
            messagebox.showerror("Error", "El número máximo de intentos por fragmento debe ser un entero.")
            return

        output_filename = self.output_filename_var.get()

        # Obtenemos el modelo directamente de la variable que se actualiza con la tabla
        technical_model_name = self.selected_model_var.get()
        if not technical_model_name:
            messagebox.showerror("Error", "Por favor, carga y selecciona un modelo de la tabla.")
            return

        if not api_key or api_key == "TU_CLAVE_API":
            messagebox.showerror("Error", "Por favor, introduce tu clave API de Gemini.")
            return
        if not pdf_paths:
            messagebox.showerror("Error", "Por favor, selecciona al menos un archivo PDF.")
            return

        try:
            # Re-initialize the generator with the current model and API key.
            # This is important if the user changes the model or API key.
            self.question_generator = QuestionGenerator(api_key, model_name=technical_model_name)
        except Exception as e:
            messagebox.showerror("Error", f"Error al inicializar el generador de preguntas: {e}")
            return

        self.update_status("Generando preguntas...")
        self.root.update_idletasks()

        existing_bank_path_for_gen = self.existing_bank_for_gen_path.get()
        bank_prompt_scope_value = self.bank_in_prompt_scope_var.get()
        prompt_example_content_value = self.prompt_example_content_var.get()
        print_raw_gemini_answer_value = self.print_raw_gemini_answer_var.get()  # Get checkbox value.

        similarity_threshold_value = None
        if self.use_similarity_filter_var.get() and existing_bank_path_for_gen:
            try:
                similarity_threshold_value = float(self.similarity_threshold_var.get())
                if not (0.0 <= similarity_threshold_value <= 1.0):
                    messagebox.showerror("Error", "El umbral de similitud debe estar entre 0.0 y 1.0.")
                    self.update_status("Error en el umbral de similitud.")
                    return
            except ValueError:
                messagebox.showerror("Error", "El umbral de similitud debe ser un número.")
                self.update_status("Error en el umbral de similitud.")
                return

        process_by_pages_value = self.process_by_pages_var.get()
        pages_per_chunk_value = 1  # Default value if not processing by pages.
        if process_by_pages_value:
            try:
                pages_per_chunk_value = int(self.pages_per_chunk_var.get())
                if pages_per_chunk_value <= 0:
                    messagebox.showerror("Error", "Las páginas por fragmento deben ser un entero positivo.")
                    self.update_status("Error en páginas por fragmento.")
                    return
            except ValueError:
                messagebox.showerror("Error", "Las páginas por fragmento deben ser un número entero.")
                self.update_status("Error en páginas por fragmento.")
                return

        bank_prompt_scope_to_pass = bank_prompt_scope_value if existing_bank_path_for_gen else None

        output_dir_value = self.gen_questions_output_dir_var.get() or None

        try:
            questions_df = self.question_generator.generate_multiple_choice_questions(
                pdf_paths=pdf_paths,
                prompt_type=selected_prompt_type,
                num_questions_per_chunk_target=num_questions_target_per_chunk,
                output_filename=output_filename,
                output_dir=output_dir_value,
                custom_prompt=custom_prompt_text_to_use,
                existing_bank_path=existing_bank_path_for_gen if existing_bank_path_for_gen else None,
                similarity_threshold=similarity_threshold_value,
                process_by_pages=process_by_pages_value,
                pages_per_chunk=pages_per_chunk_value,
                bank_prompt_scope=bank_prompt_scope_to_pass,
                prompt_example_content_type=prompt_example_content_value,
                print_raw_gemini_answer=print_raw_gemini_answer_value,
                max_generation_attempts_per_chunk=max_attempts_value
            )
            if questions_df is not None and not questions_df.empty:
                self.update_status(f"Preguntas generadas y guardadas ({len(questions_df)} en total).")
                messagebox.showinfo("Éxito", f"Preguntas generadas y guardadas ({len(questions_df)} en total).")
            else:
                # This message may appear if, after all attempts and filters, no questions are left.
                self.update_status("No se generaron preguntas o ninguna pasó los filtros.")
                messagebox.showinfo("Resultado", "No se generaron preguntas o ninguna pasó los filtros (ej. similitud, errores de API). Revisa la consola para más detalles.")
        except Exception as e:
            self.update_status(f"Error durante la generación de preguntas: {e}")
            messagebox.showerror("Error", f"Error: {e}")
            import traceback
            print(traceback.format_exc())

    def create_exam_tab(self):
        """
        Creates the 'Generate Exams' tab with all its widgets.
        """
        exam_tab = ttk.Frame(self.notebook)
        self.notebook.add(exam_tab, text='Generar Exámenes')

        # Canvas to enable scrolling
        canvas_exam = tk.Canvas(exam_tab)
        scrollbar_exam = ttk.Scrollbar(exam_tab, orient="vertical", command=canvas_exam.yview)
        canvas_exam.configure(yscrollcommand=scrollbar_exam.set)

        scrollbar_exam.pack(side="right", fill="y")
        canvas_exam.pack(side="left", fill="both", expand=True)

        # Bind mouse wheel event to the Canvas.
        canvas_exam.bind("<MouseWheel>", lambda event: canvas_exam.yview_scroll(int(-1 * (event.delta / 120)), "units"))
        # For Linux:
        canvas_exam.bind("<Button-4>", lambda event: canvas_exam.yview_scroll(-1, "units"))
        canvas_exam.bind("<Button-5>", lambda event: canvas_exam.yview_scroll(1, "units"))

        # Inner frame where we will place all the widgets
        inner_frame_exam = ttk.Frame(canvas_exam)
        inner_frame_exam.bind("<Configure>", lambda e: canvas_exam.configure(scrollregion=canvas_exam.bbox("all")))
        canvas_exam.create_window((0, 0), window=inner_frame_exam, anchor="nw")

        # Bind mouse wheel event to the inner_frame.
        inner_frame_exam.bind("<MouseWheel>", lambda event: canvas_exam.yview_scroll(int(-1 * (event.delta / 120)), "units"))
        # For Linux:
        inner_frame_exam.bind("<Button-4>", lambda event: canvas_exam.yview_scroll(-1, "units"))
        inner_frame_exam.bind("<Button-5>", lambda event: canvas_exam.yview_scroll(1, "units"))

        row = 0
        col = 0

        # 1. Excel Questions File (spans 3 columns)
        excel_label = ttk.Label(inner_frame_exam, text="Archivo Excel de Preguntas:")
        excel_label.grid(row=row, column=col, columnspan=1, padx=5, pady=5, sticky='w')
        ToolTip(excel_label, text="Seleccione la ruta del archivo Excel que contiene el banco de preguntas.")
        excel_entry = ttk.Entry(inner_frame_exam, width=40, textvariable=self.excel_filepath)
        excel_entry.grid(row=row, column=col + 1, columnspan=1, padx=5, pady=5, sticky='ew')
        ToolTip(excel_entry, text="Ruta del archivo Excel seleccionado.")
        select_button = ttk.Button(inner_frame_exam, text="Seleccionar Archivo", command=self.select_excel_file)
        select_button.grid(row=row, column=col + 2, columnspan=1, padx=5, pady=5)
        ToolTip(select_button, text="Haga clic para abrir el diálogo de selección de archivo.")
        row += 1

        # 2. Exam data group (spans 3 columns)
        exam_data_frame = ttk.LabelFrame(inner_frame_exam, text="Datos del Examen")
        exam_data_frame.grid(row=row, column=0, columnspan=3, padx=10, pady=10, sticky='ew')

        subject_label = ttk.Label(exam_data_frame, text="Asignatura:")
        subject_label.grid(row=0, column=0, padx=5, pady=5, sticky='w')
        ToolTip(subject_label, text="Ingrese el nombre de la asignatura.")
        subject_entry = ttk.Entry(exam_data_frame, width=30, textvariable=self.subject)
        subject_entry.grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        ToolTip(subject_entry, text="Nombre de la asignatura.")
        course_label = ttk.Label(exam_data_frame, text="Curso:")
        course_label.grid(row=0, column=2, padx=5, pady=5, sticky='w')
        ToolTip(course_label, text="Ingrese el curso académico (ej. 23-24).")
        course_entry = ttk.Entry(exam_data_frame, width=30, textvariable=self.course)
        course_entry.grid(row=0, column=3, padx=5, pady=5, sticky='ew')
        ToolTip(course_entry, text="Curso académico.")

        exam_name_label = ttk.Label(exam_data_frame, text="Nombre del Examen:")
        exam_name_label.grid(row=1, column=0, padx=5, pady=5, sticky='w')
        ToolTip(exam_name_label, text="Ingrese un nombre base para el examen (ej. Parcial 1).")
        exam_name_entry = ttk.Entry(exam_data_frame, width=30, textvariable=self.exam_name)
        exam_name_entry.grid(row=1, column=1, padx=5, pady=5, sticky='ew')
        ToolTip(exam_name_entry, text="Nombre base del examen.")
        num_exams_label = ttk.Label(exam_data_frame, text="Número de Exámenes a Generar:")
        num_exams_label.grid(row=2, column=0, padx=5, pady=5, sticky='w')
        ToolTip(num_exams_label, text="Indique cuántas versiones diferentes del examen desea generar.")
        num_exams_entry = ttk.Entry(exam_data_frame, width=10, textvariable=self.num_exams)
        num_exams_entry.grid(row=2, column=1, padx=5, pady=5, sticky='ew')
        ToolTip(num_exams_entry, text="Número de exámenes a generar.")

        exam_names_label = ttk.Label(exam_data_frame, text="Nombres de los Exámenes (separados por coma):")
        exam_names_label.grid(row=3, column=0, columnspan=1, padx=5, pady=5, sticky='w')
        ToolTip(exam_names_label, text="Opcional: Ingrese nombres específicos para cada examen, separados por coma (ej. Tipo A,Tipo B). Si se deja vacío, se usarán nombres genéricos.")
        exam_names_entry = ttk.Entry(exam_data_frame, width=50, textvariable=self.exam_names)
        exam_names_entry.grid(row=3, column=1, columnspan=2, padx=5, pady=5, sticky='ew')
        ToolTip(exam_names_entry, text="Nombres específicos para los exámenes (opcional).")
        row += 1

        # 3. Question selection by topic (spans the width - managed internally)
        questions_frame = ttk.LabelFrame(inner_frame_exam, text="Selección de Preguntas por Tema")
        questions_frame.grid(row=row, column=0, columnspan=3, padx=10, pady=10, sticky='ew')
        row_interno_questions = 0  # Initialize a row counter for this frame

        select_by_theme_radio = ttk.Radiobutton(questions_frame, text="Seleccionar cantidad por tema:", variable=self.selection_method_var, value="por_tema", command=self.update_theme_display)
        select_by_theme_radio.grid(row=row_interno_questions, column=0, columnspan=2, sticky='w', pady=5)
        ToolTip(select_by_theme_radio, text="Permite especificar la cantidad de preguntas a seleccionar para cada tema individualmente.")
        row_interno_questions += 1

        by_theme_labelframe = ttk.LabelFrame(questions_frame, text="Cantidad por Tema")
        by_theme_labelframe.grid(row=row_interno_questions, column=0, columnspan=2, padx=5, pady=5, sticky='ew')
        ToolTip(by_theme_labelframe, text="Configure la cantidad de preguntas para cada tema.")
        row_interno_by_theme = 0  # Internal row counter for by_theme_labelframe

        columns_frame = ttk.Frame(by_theme_labelframe)
        columns_label = ttk.Label(columns_frame, text="Número de columnas para temas:")
        columns_label.grid(row=0, column=0, sticky='w')
        ToolTip(columns_label, text="Indica el número de columnas a usar para mostrar los temas y sus cantidades.")
        columns_spinbox = ttk.Spinbox(columns_frame, from_=1, to=10, width=3, textvariable=self.num_columns_var)
        columns_spinbox.grid(row=0, column=1, padx=5)
        ToolTip(columns_spinbox, text="Número de columnas para la visualización de temas.")
        columns_frame.grid(row=row_interno_by_theme, column=0, columnspan=2, sticky='ew', pady=5)
        row_interno_by_theme += 1

        self.by_theme_frame = ttk.Frame(by_theme_labelframe)
        self.by_theme_frame.grid(row=row_interno_by_theme, column=0, sticky='nsew')  # Internal layout with grid
        row_interno_by_theme += 1

        self.theme_quantity_widgets_inner = self.by_theme_frame
        self.theme_quantity_widgets = {}

        same_number_radio = ttk.Radiobutton(questions_frame, text="Mismo número de preguntas por tema:", variable=self.selection_method_var, value="mismo_numero")
        same_number_radio.grid(row=row_interno_questions + 1, column=0, sticky='w')
        ToolTip(same_number_radio, text="Seleccione esta opción para usar la misma cantidad de preguntas para todos los temas.")
        self.num_preguntas_por_tema_entry = ttk.Entry(questions_frame, width=5, textvariable=self.num_questions_same_topic)
        self.num_preguntas_por_tema_entry.grid(row=row_interno_questions + 1, column=1, padx=5, sticky='ew')
        ToolTip(self.num_preguntas_por_tema_entry, text="Ingrese el número de preguntas a seleccionar de cada tema.")
        row_interno_questions += 2

        dictionary_radio = ttk.Radiobutton(questions_frame, text="Diccionario de preguntas por tema (Tema01:2,Tema02:3):", variable=self.selection_method_var, value="diccionario")
        dictionary_radio.grid(row=row_interno_questions + 1, column=0, sticky='w')
        ToolTip(dictionary_radio, text="Ingrese un diccionario especificando la cantidad de preguntas por tema (ej. TemaA:3,TemaB:2).")
        questions_per_topic_entry = ttk.Entry(questions_frame, textvariable=self.questions_per_topic)
        questions_per_topic_entry.grid(row=row_interno_questions + 1, column=1, padx=5, sticky='ew')
        ToolTip(questions_per_topic_entry, text="Diccionario con el formato Tema:Cantidad.")
        row += 1  # Increment the row for the next LabelFrame

        # 4. Selection method (spans 3 columns)
        method_frame = ttk.LabelFrame(inner_frame_exam, text="Método de Selección")
        method_frame.grid(row=row, column=0, columnspan=3, padx=10, pady=10, sticky='ew')
        method_label = ttk.Label(method_frame, text="Método:")
        method_label.grid(row=0, column=0, padx=5, pady=5, sticky='w')
        ToolTip(method_label, text="Seleccione el método para elegir las preguntas dentro de cada tema.")
        method_combo = ttk.Combobox(method_frame, textvariable=self.selection_method, values=["azar", "primeras", "menos usadas"], state='readonly')
        method_combo.grid(row=0, column=1, columnspan=2, padx=5, pady=5, sticky='ew')
        ToolTip(method_combo,
                text="azar: selecciona preguntas aleatoriamente. primeras: selecciona las primeras preguntas encontradas para el tema. menos usadas: selecciona las preguntas menos usadas.")
        row += 1  # Increment the row for the next LabelFrame

        # 5. Docx style (spans 3 columns)
        style_frame = ttk.LabelFrame(inner_frame_exam, text="Estilo del Documento")
        style_frame.grid(row=row, column=0, columnspan=3, padx=10, pady=10, sticky='ew')

        top_margin_label = ttk.Label(style_frame, text="Margen Superior (pulgadas):")
        top_margin_label.grid(row=0, column=0, padx=5, pady=5, sticky='w')
        ToolTip(top_margin_label, text="Define el margen superior del documento Word en pulgadas.")
        top_margin_entry = ttk.Entry(style_frame, width=5, textvariable=self.top_margin)
        top_margin_entry.grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        ToolTip(top_margin_entry, text="Margen superior en pulgadas.")
        left_margin_label = ttk.Label(style_frame, text="Margen Izquierdo (pulgadas):")
        left_margin_label.grid(row=0, column=2, padx=5, pady=5, sticky='w')
        ToolTip(left_margin_label, text="Define el margen izquierdo del documento Word en pulgadas.")
        left_margin_entry = ttk.Entry(style_frame, width=5, textvariable=self.left_margin)
        left_margin_entry.grid(row=0, column=3, padx=5, pady=5, sticky='ew')
        ToolTip(left_margin_entry, text="Margen izquierdo en pulgadas.")

        bottom_margin_label = ttk.Label(style_frame, text="Margen Inferior (pulgadas):")
        bottom_margin_label.grid(row=1, column=0, padx=5, pady=5, sticky='w')
        ToolTip(bottom_margin_label, text="Define el margen inferior del documento Word en pulgadas.")
        bottom_margin_entry = ttk.Entry(style_frame, width=5, textvariable=self.bottom_margin)
        bottom_margin_entry.grid(row=1, column=1, padx=5, pady=5, sticky='ew')
        ToolTip(bottom_margin_entry, text="Margen inferior en pulgadas.")
        right_margin_label = ttk.Label(style_frame, text="Margen Derecho (pulgadas):")
        right_margin_label.grid(row=1, column=2, padx=5, pady=5, sticky='w')
        ToolTip(right_margin_label, text="Define el margen derecho del documento Word en pulgadas.")
        right_margin_entry = ttk.Entry(style_frame, width=5, textvariable=self.right_margin)
        right_margin_entry.grid(row=1, column=3, padx=5, pady=5, sticky='ew')
        ToolTip(right_margin_entry, text="Margen derecho en pulgadas.")

        font_size_label = ttk.Label(style_frame, text="Tamaño de Fuente:")
        font_size_label.grid(row=2, column=0, padx=5, pady=5, sticky='w')
        ToolTip(font_size_label, text="Define el tamaño de la fuente para el texto del examen.")
        font_size_entry = ttk.Entry(style_frame, width=5, textvariable=self.font_size)
        font_size_entry.grid(row=2, column=1, padx=5, pady=5, sticky='ew')
        ToolTip(font_size_entry, text="Tamaño de la fuente.")
        answer_instructions_label = ttk.Label(style_frame, text="Instrucciones Hoja de Respuestas:")
        answer_instructions_label.grid(row=3, column=0, columnspan=1, padx=5, pady=5, sticky='w')
        ToolTip(answer_instructions_label, text="Ingrese las instrucciones que aparecerán en la hoja de respuestas.")
        answer_instructions_entry = ttk.Entry(style_frame, width=50, textvariable=self.answer_sheet_instructions)
        answer_instructions_entry.grid(row=3, column=1, columnspan=2, padx=5, pady=5, sticky='ew')
        ToolTip(answer_instructions_entry, text="Instrucciones para la hoja de respuestas.")
        row += 1

        # 6. Moodle configuration (spans 3 columns)
        moodle_frame = ttk.LabelFrame(inner_frame_exam, text="Configuración para Moodle")
        moodle_frame.grid(row=row, column=0, columnspan=3, padx=10, pady=10, sticky='ew')
        export_moodle_check = ttk.Checkbutton(moodle_frame, text="Exportar a Moodle XML", variable=self.export_moodle)
        export_moodle_check.grid(row=0, column=0, columnspan=3, pady=5, sticky='w')
        ToolTip(export_moodle_check, text="Marque para generar un archivo XML compatible con la importación de preguntas en Moodle.")

        penalty_label = ttk.Label(moodle_frame, text="Penalización (-%):")
        penalty_label.grid(row=1, column=0, padx=5, pady=5, sticky='w')
        ToolTip(penalty_label, text="Ingrese el porcentaje de penalización por respuesta incorrecta para la importación en Moodle (ej. -25).")
        penalty_entry = ttk.Entry(moodle_frame, width=5, textvariable=self.penalty)
        penalty_entry.grid(row=1, column=1, padx=5, pady=5, sticky='ew')
        ToolTip(penalty_entry, text="Porcentaje de penalización para Moodle.")
        xml_cat_text_label = ttk.Label(moodle_frame, text="Texto Adicional Moodle XML:")
        xml_cat_text_label.grid(row=2, column=0, columnspan=1, padx=5, pady=5, sticky='w')
        ToolTip(xml_cat_text_label, text="Opcional: Ingrese texto adicional para la categoría de las preguntas en el archivo XML de Moodle.")
        xml_cat_text_entry = ttk.Entry(moodle_frame, width=50, textvariable=self.xml_cat_additional_text)
        xml_cat_text_entry.grid(row=2, column=1, columnspan=2, padx=5, pady=5, sticky='ew')
        ToolTip(xml_cat_text_entry, text="Texto adicional para la categoría Moodle XML (opcional).")
        row += 1

        # 7. Update excel file with usage (spans 3 columns)
        update_excel_frame = ttk.Frame(inner_frame_exam)
        update_excel_frame.grid(row=row, column=0, columnspan=3, padx=10, pady=10, sticky='ew')
        update_excel_check = ttk.Checkbutton(update_excel_frame, text="Actualizar Archivo Excel con Uso", variable=self.update_excel)
        update_excel_check.pack(side='left', padx=5)
        ToolTip(update_excel_check, text="Marque para actualizar el archivo Excel indicando qué preguntas se han utilizado en el examen.")
        row += 1

        # Output path
        exam_output_dir_frame = ttk.LabelFrame(inner_frame_exam, text="Directorio de Salida para Exámenes")
        exam_output_dir_frame.grid(row=row, column=0, columnspan=3, padx=10, pady=10, sticky='ew')
        ToolTip(exam_output_dir_frame, "Carpeta donde se guardarán los exámenes generados. Si se deja en blanco, se usará la misma carpeta que el banco de preguntas.")

        exam_output_dir_entry = ttk.Entry(exam_output_dir_frame, textvariable=self.gen_exams_output_dir_var)
        exam_output_dir_entry.pack(side='left', fill='x', expand=True, padx=5, pady=5)
        ToolTip(exam_output_dir_entry, "Ruta al directorio de salida para los exámenes.")

        exam_output_dir_button = ttk.Button(exam_output_dir_frame, text="Seleccionar...", command=self.select_gen_exams_output_dir)
        exam_output_dir_button.pack(side='left', padx=5, pady=5)
        ToolTip(exam_output_dir_button, "Abrir diálogo para seleccionar el directorio de salida.")
        row += 1

        # Generate Exams Button (spans the width)
        generate_button = ttk.Button(inner_frame_exam, text="Generar Exámenes", command=self.generate_exams)
        generate_button.grid(row=row, column=0, columnspan=3, pady=20)
        ToolTip(generate_button, "Genera los archivos de examen (docx y opcionalmente xml) con la configuración actual.")

        inner_frame_exam.columnconfigure(0, weight=1)
        inner_frame_exam.columnconfigure(1, weight=1)
        inner_frame_exam.columnconfigure(2, weight=1)

    def create_manage_bank_tab(self):
        """
        Creates the 'Manage Question Bank' tab with all its widgets.
        """
        manage_bank_tab = ttk.Frame(self.notebook)
        self.notebook.add(manage_bank_tab, text='Gestionar Banco de Preguntas')

        inner_frame_manage = ttk.Frame(manage_bank_tab)
        inner_frame_manage.pack(padx=10, pady=10, fill='x')

        # --- Section to generate XLSX from a revised DOCX ---
        docx_xlsx_group = ttk.LabelFrame(inner_frame_manage, text="Generar XLSX desde DOCX revisado")
        docx_xlsx_group.pack(padx=5, pady=5, fill='x')

        # Row 0: Select Revised DOCX
        docx_label = ttk.Label(docx_xlsx_group, text="Archivo DOCX Revisado:")
        docx_label.grid(row=0, column=0, padx=5, pady=5, sticky='w')
        ToolTip(docx_label, text="Seleccione el archivo DOCX que contiene las preguntas revisadas.")

        revised_docx_entry = ttk.Entry(docx_xlsx_group, width=50, textvariable=self.revised_docx_path_var)
        revised_docx_entry.grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        ToolTip(revised_docx_entry, text="Ruta del archivo DOCX revisado.")

        docx_button = ttk.Button(docx_xlsx_group, text="Seleccionar DOCX", command=self.select_revised_docx_file)
        docx_button.grid(row=0, column=2, padx=5, pady=5)
        ToolTip(docx_button, text="Abre un diálogo para seleccionar el archivo DOCX revisado.")

        # CAMBIO: Se añade el campo para el directorio de salida en la fila 1.
        xlsx_output_dir_label = ttk.Label(docx_xlsx_group, text="Directorio de Salida (XLSX):")
        xlsx_output_dir_label.grid(row=1, column=0, padx=5, pady=5, sticky='w')
        ToolTip(xlsx_output_dir_label, "Carpeta donde se guardará el nuevo archivo XLSX. Si se deja en blanco, se usará la misma carpeta que el DOCX de entrada.")

        xlsx_output_dir_entry = ttk.Entry(docx_xlsx_group, width=50, textvariable=self.revised_xlsx_output_dir_var)
        xlsx_output_dir_entry.grid(row=1, column=1, padx=5, pady=5, sticky='ew')
        ToolTip(xlsx_output_dir_entry, "Ruta al directorio de salida para el archivo XLSX.")

        xlsx_output_dir_button = ttk.Button(docx_xlsx_group, text="Seleccionar...", command=self.select_revised_xlsx_output_dir)
        xlsx_output_dir_button.grid(row=1, column=2, padx=5, pady=5)
        ToolTip(xlsx_output_dir_button, "Abrir diálogo para seleccionar el directorio de salida.")

        # CAMBIO: Se ajusta la fila del nombre del archivo a la 2.
        xlsx_label = ttk.Label(docx_xlsx_group, text="Nombre del Nuevo Archivo XLSX:")
        xlsx_label.grid(row=2, column=0, padx=5, pady=5, sticky='w')
        ToolTip(xlsx_label, text="Ingrese el nombre para el nuevo archivo XLSX donde se guardarán las preguntas revisadas. Si se deja vacío, se usará el nombre del DOCX.")

        new_xlsx_entry = ttk.Entry(docx_xlsx_group, width=50, textvariable=self.new_xlsx_filename_var)
        new_xlsx_entry.grid(row=2, column=1, padx=5, pady=5, sticky='ew')
        ToolTip(new_xlsx_entry, text="Nombre del archivo XLSX de salida.")
        xlsx_button = ttk.Button(docx_xlsx_group, text="Guardar XLSX Revisado", command=self.save_revised_questions_to_xlsx)
        xlsx_button.grid(row=2, column=2, padx=5, pady=5)
        ToolTip(xlsx_button, text="Guarda las preguntas revisadas en un nuevo archivo XLSX.")

        docx_xlsx_group.columnconfigure(1, weight=1)

        # --- Section to add questions from another bank ---
        add_from_bank_frame = ttk.LabelFrame(inner_frame_manage, text="Añadir Preguntas Existentes")
        add_from_bank_frame.pack(padx=5, pady=10, fill='x')

        existing_bank_label = ttk.Label(add_from_bank_frame, text="Banco Existente:")
        existing_bank_label.grid(row=0, column=0, padx=5, pady=5, sticky='w')
        ToolTip(existing_bank_label, text="Seleccione el archivo XLSX del banco de preguntas existente al que se añadirán las nuevas preguntas.")

        existing_bank_entry = ttk.Entry(add_from_bank_frame, width=40, textvariable=self.existing_bank_path)
        existing_bank_entry.grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        ToolTip(existing_bank_entry, text="Ruta del archivo XLSX del banco de preguntas existente.")

        select_existing_button = ttk.Button(add_from_bank_frame, text="Seleccionar", command=self.select_existing_bank_file)
        select_existing_button.grid(row=0, column=2, padx=5, pady=5)
        ToolTip(select_existing_button, text="Abre un diálogo para seleccionar el archivo XLSX del banco de preguntas existente.")

        reviewed_add_label = ttk.Label(add_from_bank_frame, text="Archivo a Añadir:")
        reviewed_add_label.grid(row=1, column=0, padx=5, pady=5, sticky='w')
        ToolTip(reviewed_add_label, text="Seleccione el archivo XLSX que contiene las preguntas que desea añadir al banco existente.")

        reviewed_add_entry = ttk.Entry(add_from_bank_frame, width=40, textvariable=self.reviewed_add_path)
        reviewed_add_entry.grid(row=1, column=1, padx=5, pady=5, sticky='ew')
        ToolTip(reviewed_add_entry, text="Ruta del archivo XLSX con las preguntas a añadir.")

        select_add_button = ttk.Button(add_from_bank_frame, text="Seleccionar", command=self.select_reviewed_file_to_add)
        select_add_button.grid(row=1, column=2, padx=5, pady=5)
        ToolTip(select_add_button, text="Abre un diálogo para seleccionar el archivo XLSX con las preguntas a añadir.")

        duplicate_criteria_frame = ttk.LabelFrame(add_from_bank_frame, text="Criterio de Duplicado")
        duplicate_criteria_frame.grid(row=2, column=0, columnspan=3, padx=5, pady=5, sticky='ew')
        ToolTip(duplicate_criteria_frame, text="Seleccione el criterio para determinar si una pregunta ya existe en el banco de preguntas.")

        check_pregunta_unica = ttk.Radiobutton(duplicate_criteria_frame, text="Pregunta Única (ignorar respuestas)", variable=self.duplicate_check_var, value="pregunta_unica")
        check_pregunta_unica.pack(side='left', padx=10)
        ToolTip(check_pregunta_unica, text="Solo se compara el texto de la pregunta para detectar duplicados. Las respuestas no se tienen en cuenta. Solo se añade si la pregunta es diferente.")

        check_pregunta_respuestas = ttk.Radiobutton(duplicate_criteria_frame, text="Pregunta y Respuestas Iguales", variable=self.duplicate_check_var, value="pregunta_respuestas")
        check_pregunta_respuestas.pack(side='left', padx=10)
        ToolTip(check_pregunta_respuestas,
                text="Se compara el texto de la pregunta y todas las opciones de respuesta para detectar duplicados. Solo se añade si la pregunta o alguna de sus respuestas son diferentes.")

        filter_state_frame = ttk.LabelFrame(add_from_bank_frame, text="Filtro de Estado")
        filter_state_frame.grid(row=3, column=0, columnspan=3, padx=5, pady=5, sticky='ew')
        ToolTip(filter_state_frame, text="Elija si desea añadir todas las preguntas del archivo o solo las que están marcadas como 'Aceptable'.")

        add_all_radio = ttk.Radiobutton(filter_state_frame, text="Añadir todas las preguntas", variable=self.add_questions_filter_var, value="todas")
        add_all_radio.pack(side='left', padx=10)
        ToolTip(add_all_radio, text="Se intentarán añadir todas las preguntas del archivo de origen, sin importar su estado.")

        add_acceptable_radio = ttk.Radiobutton(filter_state_frame, text="Añadir solo con estado 'Aceptable'", variable=self.add_questions_filter_var, value="aceptable")
        add_acceptable_radio.pack(side='left', padx=10)
        ToolTip(add_acceptable_radio, text="Solo se añadirán las preguntas del archivo de origen que tengan 'Aceptable' en la columna 'Estado'.")

        add_button = ttk.Button(add_from_bank_frame, text="Añadir Preguntas sin Duplicados", command=self.add_reviewed_questions_to_bank)
        add_button.grid(row=4, column=0, columnspan=3, pady=10)
        ToolTip(add_button, text="Inicia el proceso de añadir las preguntas del archivo seleccionado al banco existente, evitando duplicados según el criterio elegido.")

        add_from_bank_frame.columnconfigure(1, weight=1)

    def select_revised_docx_file(self) -> None:
        """
        Opens a dialog to select a revised DOCX file.
        The path of the selected file is saved in the `self.revised_docx_path_var` variable.
        """
        filepath = filedialog.askopenfilename(
            title="Seleccionar Archivo DOCX Revisado",
            filetypes=[("Archivos Word", "*.docx")]
        )
        if filepath:
            self.revised_docx_path_var.set(filepath)

    def save_revised_questions_to_xlsx(self) -> None:
        """
        Saves revised questions from a DOCX file to a new XLSX file.
        It uses the `QuestionBankManager` class to read the DOCX. If no name is provided
        for the XLSX file, one is generated automatically based on the DOCX name.
        """
        revised_docx_path = self.revised_docx_path_var.get()
        new_xlsx_filename = self.new_xlsx_filename_var.get()
        output_dir_value = self.revised_xlsx_output_dir_var.get() or None
        question_bank_manager = QuestionBankManager()

        if not revised_docx_path:
            messagebox.showerror("Error", "Por favor, seleccione un archivo DOCX revisado.")
            return

        if not new_xlsx_filename:
            base_name = os.path.splitext(os.path.basename(revised_docx_path))[0]
            new_xlsx_filename = f"{base_name}.xlsx"
        elif not new_xlsx_filename.endswith(".xlsx"):
            new_xlsx_filename += ".xlsx"

        saved_path = question_bank_manager.generate_excel_from_docx(
            docx_path=revised_docx_path,
            excel_output_filename=new_xlsx_filename,
            output_dir=output_dir_value
        )

        if saved_path:
            messagebox.showinfo("Guardado", f"Las preguntas revisadas se han guardado en: {saved_path}")
        else:
            messagebox.showerror("Error al Guardar", "Ocurrió un error al generar el archivo XLSX. Revise la consola para más detalles.")

    def load_themes_for_selection(self) -> None:
        """
        Loads themes from an Excel file for the 'questions per theme' selection UI.
        It reads the 'Tema' column and dynamically creates Spinbox widgets for each unique theme.
        """
        # Clear existing widgets
        for widget in self.by_theme_frame.winfo_children():
            widget.destroy()
        self.theme_quantity_widgets = {}  # Reset the widget dictionary.

        excel_path = self.excel_filepath.get()
        if os.path.exists(excel_path):
            try:
                df = pd.read_excel(excel_path)
                if 'Tema' in df.columns:
                    unique_themes = sorted(df['Tema'].unique())
                    try:
                        num_cols = int(self.num_columns_var.get())
                        if num_cols < 1:
                            num_cols = 1  # Ensure at least 1 column.
                    except ValueError:
                        num_cols = 3  # Default value if not a valid number.

                    num_themes = len(unique_themes)
                    row = 0
                    col = 0

                    for i, theme in enumerate(unique_themes):
                        theme_frame = ttk.Frame(self.by_theme_frame)
                        theme_frame.grid(row=row, column=col, padx=5, pady=2, sticky='ew')
                        ttk.Label(theme_frame, text=f"{theme}:").pack(side='left')
                        quantity_spinbox = tk.Spinbox(theme_frame, from_=0, to=100, width=3)  # Adjustable range.
                        quantity_spinbox.pack(side='left', padx=5)
                        self.theme_quantity_widgets[theme] = quantity_spinbox

                        col += 1
                        if col >= num_cols:
                            col = 0
                            row += 1

                    # Ensure the inner frame adjusts to its content.
                    self.by_theme_frame.update_idletasks()
                    self.by_theme_frame.config(width=self.by_theme_frame.winfo_width())

                else:
                    print("Advertencia: La columna 'Tema' no se encontró en el archivo Excel.")
            except Exception as e:
                print(f"Error al leer el archivo Excel para cargar temas: {e}")
        else:
            print(f"Advertencia: El archivo Excel '{excel_path}' no se encuentra para cargar temas.")

    def update_theme_display(self) -> None:
        """
        Reloads themes when the 'select by theme' option changes.
        This method clears or loads the theme selection widgets depending
        on whether the 'select by theme' option is enabled or not.
        """
        if self.selection_method_var.get() == "por_tema":
            self.load_themes_for_selection()
        else:
            # Clear theme widgets if this option is not selected.
            for widget in self.by_theme_frame.winfo_children():
                widget.destroy()
            self.theme_quantity_widgets = {}

    def select_excel_file(self) -> None:
        """
        Opens a dialog to select an Excel file.
        The path of the selected file is saved in the `self.excel_filepath` variable.
        After selecting the file, `self.load_themes_for_selection()` is called to load the themes.
        """
        filepath = filedialog.askopenfilename(
            initialdir=".",
            title="Seleccionar archivo Excel",
            filetypes=(("Archivos Excel", "*.xlsx *.xls"), ("Todos los archivos", "*.*"))
        )
        if filepath:
            self.excel_filepath.set(filepath)
            # Load themes after selecting a file.
            self.load_themes_for_selection()

    def generate_exams(self) -> None:
        """
        Gathers all parameters from the 'Generate Exams' tab and triggers the exam generation process.
        It validates user input, constructs the `questions_per_topic` dictionary, and calls the
        `generate_exam_from_excel` method from the backend `ExamGenerator` class.
        """
        excel_path = self.excel_filepath.get()
        subject = self.subject.get()
        exam_name = self.exam_name.get()
        course = self.course.get()
        num_exams_str = self.num_exams.get()
        exam_names_str = self.exam_names.get()
        selection_method_var = self.selection_method_var.get()  # Get the selection method from the UI.
        selection_method = self.selection_method.get()  # General selection method (azar, primeras, etc.).
        top_margin_str = self.top_margin.get()
        bottom_margin_str = self.bottom_margin.get()
        left_margin_str = self.left_margin.get()
        right_margin_str = self.right_margin.get()
        font_size_str = self.font_size.get()
        answer_sheet_instructions = self.answer_sheet_instructions.get()
        penalty_str = self.penalty.get()
        xml_cat_additional_text = self.xml_cat_additional_text.get()
        export_moodle = self.export_moodle.get()
        update_excel = self.update_excel.get()

        if not os.path.exists(excel_path):
            messagebox.showerror("Error", f"El archivo Excel '{excel_path}' no se encuentra.")
            return

        try:
            num_exams = int(num_exams_str) if num_exams_str else 2
            top_margin = float(top_margin_str) if top_margin_str else 1
            bottom_margin = float(bottom_margin_str) if bottom_margin_str else 1
            left_margin = float(left_margin_str) if left_margin_str else 0.5
            right_margin = float(right_margin_str) if right_margin_str else 0.5
            font_size = int(font_size_str) if font_size_str else 9
            penalty = int(penalty_str) if penalty_str else -25
        except ValueError:
            messagebox.showerror("Error", "Por favor, introduce valores numéricos válidos para los márgenes, tamaño de fuente, número de exámenes y penalización.")
            return

        exam_name_list = [name.strip() for name in exam_names_str.split(',')] if exam_names_str else None

        questions_per_topic = {}

        if selection_method_var == "diccionario":
            if self.questions_per_topic.get():
                try:
                    for item in self.questions_per_topic.get().split(','):
                        topic, quantity = item.strip().split(':')
                        questions_per_topic[topic.strip()] = int(quantity.strip())
                except ValueError:
                    messagebox.showerror("Error", "Formato incorrecto para 'Diccionario de preguntas por tema'. Debe ser 'Tema 01:2, Tema 02:3', etc.")
                    return
        elif selection_method_var == "mismo_numero":
            num_preguntas_str = self.num_preguntas_por_tema_entry.get()
            if num_preguntas_str:
                try:
                    num_preguntas = int(num_preguntas_str)
                    df_temp = pd.read_excel(excel_path)
                    if 'Tema' in df_temp.columns:
                        unique_themes = df_temp['Tema'].unique()
                        for theme in unique_themes:
                            questions_per_topic[theme] = num_preguntas
                    else:
                        messagebox.showerror("Error", "La columna 'Tema' no se encontró en el archivo Excel.")
                        return
                except ValueError:
                    messagebox.showerror("Error", "Por favor, introduce un número entero válido para 'Mismo número de preguntas por tema'.")
                    return
            else:
                messagebox.showinfo("Información", "Por favor, introduce el número de preguntas por tema.")
                return
        elif selection_method_var == "por_tema":
            df_temp = pd.read_excel(excel_path)
            if 'Tema' in df_temp.columns:
                unique_themes = df_temp['Tema'].unique()
                for theme in unique_themes:
                    if theme in self.theme_quantity_widgets:
                        quantity_str = self.theme_quantity_widgets[theme].get()
                        try:
                            quantity = int(quantity_str)
                            if quantity > 0:  # Only include themes with quantity greater than 0.
                                questions_per_topic[theme] = quantity
                        except ValueError:
                            messagebox.showerror("Error", f"Por favor, introduce un número entero válido para la cantidad de preguntas del tema '{theme}'.")
                            return
            else:
                messagebox.showerror("Error", "La columna 'Tema' no se encontró en el archivo Excel.")
                return

        output_dir_value = self.gen_exams_output_dir_var.get() or None

        self.update_status("Generando exámenes...")
        try:
            self.exam_generator.generate_exam_from_excel(
                bank_excel_path=excel_path,
                output_dir=output_dir_value,
                exam_names=exam_name_list,
                questions_per_topic=questions_per_topic,
                selection_method=selection_method,
                subject=subject,
                exam=exam_name,
                course=course,
                num_exams=num_exams,
                top_margin=top_margin,
                bottom_margin=bottom_margin,
                left_margin=left_margin,
                right_margin=right_margin,
                export_moodle_xml=export_moodle,
                font_size=font_size,
                xml_cat_additional_text=xml_cat_additional_text,
                penalty=penalty,
                update_excel=update_excel,
                answer_sheet_instructions=answer_sheet_instructions
            )
            self.update_status("Exámenes generados.")
            messagebox.showinfo("Éxito", "Exámenes generados correctamente.")
        except Exception as e:
            self.update_status(f"Error al generar exámenes: {e}")
            messagebox.showerror("Error", f"Ocurrió un error al generar los exámenes: {e}")

    def select_existing_bank_file(self) -> None:
        """
        Opens a dialog for the user to select an existing Excel file
        that contains the question bank.
        The path of the selected file is saved in the `self.existing_bank_path` variable.
        """
        filepath = filedialog.askopenfilename(
            title="Seleccionar Archivo Excel Existente",
            filetypes=[("Archivos Excel", "*.xlsx;*.xls")]
        )
        if filepath:
            self.existing_bank_path.set(filepath)

    def select_reviewed_file_to_add(self) -> None:
        """
        Opens a dialog for the user to select a revised Excel file
        containing questions to add to the existing question bank.
        The path of the selected file is saved in the `self.reviewed_add_path` variable.
        """
        filepath = filedialog.askopenfilename(
            title="Seleccionar Archivo Excel Revisado",
            filetypes=[("Archivos Excel", "*.xlsx;*.xls")]
        )
        if filepath:
            self.reviewed_add_path.set(filepath)

    def add_reviewed_questions_to_bank(self) -> None:
        """
        Adds questions from a reviewed Excel file to an existing question bank,
        avoiding duplicates based on the selected criteria.
        """
        existing_bank_path = self.existing_bank_path.get()
        reviewed_add_path = self.reviewed_add_path.get()
        duplicate_criteria = self.duplicate_check_var.get()
        duplicate_check_columns = ['Pregunta']  # Default criteria.

        if duplicate_criteria == "pregunta_respuestas":
            duplicate_check_columns = ['Pregunta', 'Respuesta A', 'Respuesta B', 'Respuesta C', 'Respuesta D']

        if not existing_bank_path or not reviewed_add_path:
            messagebox.showerror("Error", "Por favor, seleccione ambos archivos.")
            return

        # Determine the boolean value from user selection.
        only_acceptable = (self.add_questions_filter_var.get() == "aceptable")

        # Pass the new boolean argument to the backend method.
        added_count, df_updated = self.question_bank_manager.add_questions_without_duplicates(
            existing_bank_path,
            reviewed_add_path,
            duplicate_check_columns=duplicate_check_columns,
            add_only_acceptable=only_acceptable
        )

        if added_count == -1:
            messagebox.showerror("Error", "Error al procesar los archivos.")
            return

        if added_count > 0:
            response = messagebox.askyesnocancel("Guardar Cambios",
                                                 f"Se añadieron {added_count} preguntas nuevas. ¿Desea guardar los cambios en el archivo existente?",
                                                 default='yes')
            if response is True:
                filepath = self.question_bank_manager.save_dataframe_to_excel(df_updated, existing_bank_path, overwrite=True)
                if filepath:
                    messagebox.showinfo("Éxito", f"Se añadieron {added_count} preguntas al archivo existente: {filepath}")
                else:
                    messagebox.showerror("Error al guardar", "Error al guardar el archivo existente.")
            elif response is False:
                new_filepath = filedialog.asksaveasfilename(
                    title="Guardar Banco de Preguntas Actualizado Como...",
                    defaultextension=".xlsx",
                    initialdir=os.path.dirname(existing_bank_path),
                    initialfile=f"{os.path.splitext(os.path.basename(existing_bank_path))[0]}_actualizado.xlsx"
                )
                if new_filepath:
                    filepath = self.question_bank_manager.save_dataframe_to_excel(df_updated, new_filepath, overwrite=True)
                    if filepath:
                        messagebox.showinfo("Éxito", f"Se guardaron {added_count} preguntas en: {filepath}")
                    else:
                        messagebox.showerror("Error al guardar", "Error al guardar el nuevo archivo.")
        else:
            messagebox.showinfo("Información", "No se encontraron preguntas nuevas para añadir.")

    def show_about_dialog(self):
        """Displays an 'About' dialog with program and license information."""
        about_text = (
            "ExamGenerator\n\n"
            "Copyright (C) 2024 Daniel Sánchez-García\n\n"
            "Este programa es software libre: usted puede redistribuirlo y/o modificarlo "
            "bajo los términos de la Licencia Pública General de GNU publicada por la "
            "Free Software Foundation, ya sea la versión 3 de la Licencia, o "
            "(a su opción) cualquier versión posterior.\n\n"
            "Este programa se distribuye con la esperanza de que sea útil, pero SIN NINGUNA GARANTÍA; "
            "sin siquiera la garantía implícita de COMERCIABILIDAD o APTITUD PARA UN PROPÓSITO PARTICULAR. "
            "Consulte la Licencia Pública General de GNU para más detalles."
        )
        messagebox.showinfo("Acerca de ExamGenerator", about_text, parent=self.root)

    def select_gen_questions_output_dir(self) -> None:
        """Opens a dialog to select the output directory for generated questions."""
        directory = filedialog.askdirectory(title="Seleccionar Directorio de Salida para Preguntas Generadas")
        if directory:
            self.gen_questions_output_dir_var.set(directory)

    def select_revised_xlsx_output_dir(self) -> None:
        """Opens a dialog to select the output directory for the revised XLSX file."""
        directory = filedialog.askdirectory(title="Seleccionar Directorio de Salida para XLSX Revisado")
        if directory:
            self.revised_xlsx_output_dir_var.set(directory)

    def select_gen_exams_output_dir(self) -> None:
        """Opens a dialog to select the output directory for generated exams."""
        directory = filedialog.askdirectory(title="Seleccionar Directorio de Salida para Exámenes")
        if directory:
            self.gen_exams_output_dir_var.set(directory)

def main():
    root = tk.Tk()
    app = ExamApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()