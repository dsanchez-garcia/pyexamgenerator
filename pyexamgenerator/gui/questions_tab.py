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

"""The «Generar Preguntas» tab (ARC-1): questions from PDFs or images with Gemini, the API key, the
models table and the custom prompt types.
"""

import logging
import os
import tkinter as tk
from tkinter import filedialog, scrolledtext, ttk
from typing import Dict, Optional

from google import genai

from pyexamgenerator import credentials, gui_logic, user_config
from pyexamgenerator.gui._dialogs import messagebox
from pyexamgenerator.question_generator import (
    GeminiRequestError,
    QuestionGenerator,
    QuotaExceededError,
    ServiceOverloadedError,
)
from pyexamgenerator.tooltip import ToolTip

logger = logging.getLogger(__name__)


class QuestionsTab:
    """Widgets, variables and actions of the «Generar Preguntas» tab.

    ``app`` is the :class:`~pyexamgenerator.main_app.ExamApp` that owns the window: the tab uses its
    notebook, status bar, page-scroll helpers and background tasks.
    """

    def __init__(self, app) -> None:
        self.app = app
        # Clave de API: la variable de entorno GEMINI_API_KEY o, si no está, la guardada con
        # «Guardar Clave» en el almacén de credenciales del sistema (SEC-3, `credentials.py`).
        self.api_key = credentials.get_api_key()
        self.question_generator: Optional[QuestionGenerator] = None
        self.prompt_types = self.load_prompt_types()
        self.selected_prompt_type = tk.StringVar()
        self.custom_prompt_text = tk.StringVar()
        self.pdf_files_var = tk.StringVar()
        self.num_questions_var = tk.StringVar(value="5")
        self.output_filename_var = tk.StringVar(value="preguntas")
        self.api_key_var = tk.StringVar(value=self.api_key if self.api_key else credentials.PLACEHOLDER)
        self.gen_questions_output_dir_var = tk.StringVar()
        self.selected_model_var = tk.StringVar(value='')
        self.existing_bank_for_gen_path = tk.StringVar()
        self.input_mode_var = tk.StringVar(value="text")
        self.process_by_pages_var = tk.BooleanVar(value=False)
        self.pages_per_chunk_var = tk.StringVar(value="1")
        self.total_chunks_var = tk.StringVar(value="")
        self.chunking_mode_var = tk.StringVar(value="pages")
        self.max_attempts_var = tk.StringVar(value="3")
        self.print_raw_gemini_answer_var = tk.BooleanVar(value=False)
        self.use_similarity_filter_var = tk.BooleanVar(value=True)
        self.similarity_threshold_var = tk.StringVar(value="0.8")
        self.bank_in_prompt_scope_var = tk.StringVar(value="mismo_tema")
        self.prompt_example_content_var = tk.StringVar(value="solo_enunciados")
        self.include_similar_questions_in_prompt_var = tk.BooleanVar(value=True)
        # Añadimos variables para gestionar el tooltip de la tabla de modelos
        self.tree_tooltip = None
        self.last_hovered_cell = (None, None)  # Almacenará (row_id, col_id)

        self.create_question_tab()

    def load_prompt_types(self) -> Dict[str, str]:
        """
        Loads custom prompt types from a JSON file.

        Returns:
            Dict[str, str]: A dictionary where keys are prompt type names
                           and values are the prompt texts.
        """
        # In the user's configuration folder, not in the current one (ARC-12).
        custom_prompts: Dict[str, str] = {}
        try:
            custom_prompts = user_config.read_json(user_config.PROMPTS_FILE) or {}
        except (OSError, ValueError):
            path = user_config.config_path(user_config.PROMPTS_FILE)
            messagebox.showerror("Error", f"Error al decodificar el archivo de prompts personalizados:\n{path}")

        default_prompts = self.load_default_prompt_types()

        # Combina ambos, dando prioridad a los personalizados si hay un conflicto de nombres.
        return {**default_prompts, **custom_prompts}

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
            "PM": "Genera preguntas tipo test de opción múltiple enfocadas en Gestión de Proyectos.",
        }

    def save_prompt_types(self) -> None:
        """
        Saves custom prompt types to a JSON file in the user's configuration folder.
        """
        # Filtra para guardar solo los prompts que no son los predeterminados.
        custom_prompts = {k: v for k, v in self.prompt_types.items() if k not in self.load_default_prompt_types()}
        try:
            user_config.write_json(user_config.PROMPTS_FILE, custom_prompts)
        except OSError as exc:
            messagebox.showerror("Error", f"No se pudieron guardar los prompts personalizados:\n{exc}")

    def add_edit_prompt_type(self, existing_type: Optional[str] = None) -> None:
        """
        Opens a Toplevel window to add a new prompt type or edit an existing one.
        """
        add_window = tk.Toplevel(self.app.root)
        title = "Editar Tipo de Prompt" if existing_type else "Añadir Nuevo Tipo de Prompt"
        add_window.title(title)

        ttk.Label(add_window, text="Nombre del Tipo (ej. 'Historia'):").grid(
            row=0, column=0, padx=10, pady=5, sticky='w'
        )
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
                messagebox.showerror(
                    "Error", "El nombre del tipo y el texto del prompt no pueden estar vacíos.", parent=add_window
                )
                return

            if new_type != existing_type and new_type in self.prompt_types:
                if not messagebox.askyesno(
                    "Sobrescribir", f"El tipo '{new_type}' ya existe. ¿Desea sobrescribirlo?", parent=add_window
                ):
                    return

            if existing_type and new_type != existing_type:
                # Renaming a custom type: drop the old name instead of keeping both.
                self.prompt_types.pop(existing_type, None)
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
        add_window.transient(self.app.root)
        try:
            add_window.grab_set()
        except tk.TclError:
            pass  # e.g. X11 before the window is viewable; the dialog still works without the grab.

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

        if messagebox.askyesno(
            "Confirmar Eliminación",
            f"¿Está seguro de que desea eliminar permanentemente el tipo de prompt '{selected_type}'?",
        ):
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

    def toggle_pages_per_chunk_entry(self):
        """
        Enables or disables the 'pages per chunk' entry based on the checkbox state.
        """
        if self.process_by_pages_var.get():
            self.pages_per_chunk_entry.config(state='normal')
            self.total_chunks_entry.config(state='normal')
            self.chunking_mode_combo.config(state='readonly')
        else:
            self.pages_per_chunk_entry.config(state='disabled')
            self.total_chunks_entry.config(state='disabled')
            self.chunking_mode_combo.config(state='disabled')

    def create_question_tab(self) -> None:
        """
        Creates the 'Generate Questions' tab with all its widgets.
        """
        canvas_question, inner_frame_question = self.app._create_scrollable_tab('Generar Preguntas')

        # --- Prompts and PDF section ---
        prompt_type_frame = ttk.LabelFrame(inner_frame_question, text="Seleccionar/Editar Tipo de Prompt")
        prompt_type_frame.pack(padx=10, pady=10, fill='x')

        prompt_type_label = ttk.Label(prompt_type_frame, text="Tipo de Prompt:")
        prompt_type_label.grid(row=0, column=0, padx=5, pady=5, sticky='w')
        ToolTip(prompt_type_label, "Seleccione el prompt base para la generación de preguntas.")
        prompt_type_names = list(self.prompt_types.keys())
        self.prompt_type_combo = ttk.Combobox(
            prompt_type_frame, textvariable=self.selected_prompt_type, values=prompt_type_names, state='readonly'
        )
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

        edit_prompt_button = ttk.Button(
            prompt_buttons_frame,
            text="Editar",
            command=lambda: self.add_edit_prompt_type(existing_type=self.selected_prompt_type.get()),
        )
        edit_prompt_button.pack(side='left', padx=2)
        ToolTip(edit_prompt_button, "Editar el tipo de prompt seleccionado actualmente.")

        delete_prompt_button = ttk.Button(prompt_buttons_frame, text="Eliminar", command=self.delete_prompt_type)
        delete_prompt_button.pack(side='left', padx=2)
        ToolTip(
            delete_prompt_button, "Eliminar el tipo de prompt seleccionado (no se pueden eliminar los predeterminados)."
        )

        prompt_type_frame.columnconfigure(1, weight=1)

        selected_prompt_frame = ttk.LabelFrame(inner_frame_question, text="Prompt Seleccionado")
        selected_prompt_frame.pack(padx=10, pady=10, fill='both', expand=True)
        self.prompt_text_display = scrolledtext.ScrolledText(selected_prompt_frame, state=tk.DISABLED)
        self.prompt_text_display.pack(padx=5, pady=5, fill='both', expand=True)
        self.update_custom_prompt_display()
        ToolTip(self.prompt_text_display, "Texto del prompt seleccionado. No editable directamente aquí.")

        pdf_frame = ttk.LabelFrame(inner_frame_question, text="Seleccionar Archivos Fuente")
        pdf_frame.pack(padx=10, pady=10, fill='x')
        pdf_label = ttk.Label(pdf_frame, text="Archivos PDF/Imagen:")
        pdf_label.grid(row=0, column=0, padx=5, pady=5, sticky='w')
        ToolTip(pdf_label, "Seleccione PDFs o imágenes desde los cuales se generarán las preguntas.")
        self.pdf_entry = ttk.Entry(pdf_frame, width=50, textvariable=self.pdf_files_var)
        self.pdf_entry.grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        ToolTip(
            self.pdf_entry,
            "Rutas de los archivos seleccionados, separadas por ';' (un nombre de archivo puede contener comas).",
        )
        select_pdf_button = ttk.Button(pdf_frame, text="Seleccionar Archivos", command=self.select_pdf_files)
        select_pdf_button.grid(row=0, column=2, padx=5, pady=5)
        ToolTip(select_pdf_button, "Abre un diálogo para seleccionar uno o más PDFs o imágenes.")

        input_mode_label = ttk.Label(pdf_frame, text="Modo de entrada:")
        input_mode_label.grid(row=1, column=0, padx=5, pady=5, sticky='w')
        ToolTip(
            input_mode_label,
            "text: extrae texto del PDF; image: analiza contenido visual (imágenes o páginas renderizadas).",
        )
        input_mode_combo = ttk.Combobox(
            pdf_frame, textvariable=self.input_mode_var, values=["text", "image"], state='readonly', width=12
        )
        input_mode_combo.grid(row=1, column=1, padx=5, pady=5, sticky='w')
        ToolTip(input_mode_combo, "Selecciona cómo Gemini debe interpretar los archivos fuente.")
        pdf_frame.columnconfigure(1, weight=1)

        # --- Generation configuration section ---
        config_frame = ttk.LabelFrame(inner_frame_question, text="Configuración de Generación")
        config_frame.pack(padx=10, pady=10, fill='x', expand=True)

        # Row 0: Target questions per PDF/chunk
        num_questions_label = ttk.Label(config_frame, text="Preguntas objetivo por PDF/fragmento:")
        num_questions_label.grid(row=0, column=0, padx=5, pady=5, sticky='w')
        ToolTip(
            num_questions_label, "El número de preguntas que la aplicación intentará generar para cada PDF o fragmento."
        )
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
        process_by_pages_check = ttk.Checkbutton(
            processing_frame,
            text="Procesar PDF por fragmentos",
            variable=self.process_by_pages_var,
            command=self.toggle_pages_per_chunk_entry,
        )
        process_by_pages_check.grid(row=0, column=0, padx=5, pady=5, sticky='w')
        ToolTip(
            process_by_pages_check,
            "Si se marca, el PDF se dividirá en fragmentos más pequeños para la generación. Útil para documentos grandes.",
        )
        pages_per_chunk_label = ttk.Label(processing_frame, text="Páginas por fragmento:")
        pages_per_chunk_label.grid(row=0, column=1, padx=5, pady=5, sticky='w')
        ToolTip(pages_per_chunk_label, "Número de páginas a incluir en cada fragmento de procesamiento.")
        self.pages_per_chunk_entry = ttk.Entry(
            processing_frame, width=5, textvariable=self.pages_per_chunk_var, state='disabled'
        )
        self.pages_per_chunk_entry.grid(row=0, column=2, padx=5, pady=5, sticky='w')
        ToolTip(self.pages_per_chunk_entry, "Introduzca el número de páginas para cada fragmento.")

        total_chunks_label = ttk.Label(processing_frame, text="Fragmentos totales (opcional):")
        total_chunks_label.grid(row=0, column=3, padx=5, pady=5, sticky='w')
        ToolTip(total_chunks_label, "Si se indica, divide cada PDF en ese número total de fragmentos.")
        self.total_chunks_entry = ttk.Entry(
            processing_frame, width=6, textvariable=self.total_chunks_var, state='disabled'
        )
        self.total_chunks_entry.grid(row=0, column=4, padx=5, pady=5, sticky='w')

        chunking_mode_label = ttk.Label(processing_frame, text="Modo:")
        chunking_mode_label.grid(row=0, column=5, padx=5, pady=5, sticky='w')
        self.chunking_mode_combo = ttk.Combobox(
            processing_frame,
            textvariable=self.chunking_mode_var,
            values=["pages", "text_length"],
            state='disabled',
            width=12,
        )
        self.chunking_mode_combo.grid(row=0, column=6, padx=5, pady=5, sticky='w')
        ToolTip(self.chunking_mode_combo, "pages: divide por páginas; text_length: divide por longitud de texto.")

        # Row 3: Max attempts per chunk
        max_attempts_label = ttk.Label(config_frame, text="Máx. intentos por fragmento:")
        max_attempts_label.grid(row=3, column=0, padx=5, pady=5, sticky='w')
        ToolTip(
            max_attempts_label,
            "Número máximo de veces que se llamará a la API para un único fragmento si no se alcanza el objetivo de preguntas.",
        )
        max_attempts_entry = ttk.Entry(config_frame, width=5, textvariable=self.max_attempts_var)
        max_attempts_entry.grid(row=3, column=1, padx=5, pady=5, sticky='w')
        ToolTip(
            max_attempts_entry,
            "Número máximo de intentos de generación por fragmento si no se alcanza el objetivo (Recomendado: 3).\nAfecta al uso de la API de Gemini (más intentos = más uso y posible límite diario).",
        )

        # Row 4: Duplicate Filter
        similarity_filter_frame = ttk.LabelFrame(config_frame, text="Filtro de Duplicados")
        similarity_filter_frame.grid(row=4, column=0, columnspan=3, padx=5, pady=5, sticky='ew')
        ToolTip(
            similarity_filter_frame,
            "Compara cada pregunta generada con un banco existente y descarta las que sean muy parecidas (basado solo en el enunciado).",
        )

        existing_bank_label = ttk.Label(similarity_filter_frame, text="Banco Existente a Consultar:")
        existing_bank_label.grid(row=0, column=0, padx=5, pady=5, sticky='w')
        ToolTip(
            existing_bank_label, "Seleccione un archivo Excel con preguntas existentes para evitar generar duplicados."
        )
        existing_bank_entry = ttk.Entry(similarity_filter_frame, textvariable=self.existing_bank_for_gen_path)
        existing_bank_entry.grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        ToolTip(existing_bank_entry, "Ruta al archivo del banco de preguntas existente.")
        select_existing_button = ttk.Button(
            similarity_filter_frame, text="Seleccionar", command=self.select_existing_bank_for_gen_file
        )
        select_existing_button.grid(row=0, column=2, padx=5, pady=5)
        ToolTip(select_existing_button, "Abre un diálogo para seleccionar el archivo del banco de preguntas.")
        similarity_filter_frame.columnconfigure(1, weight=1)

        use_similarity_check = ttk.Checkbutton(
            similarity_filter_frame, text="Activar filtro de similitud", variable=self.use_similarity_filter_var
        )
        use_similarity_check.grid(row=1, column=0, padx=5, pady=2, sticky='w')
        ToolTip(
            use_similarity_check,
            "Si se marca, las preguntas generadas se compararán con el banco existente y se descartarán si son demasiado similares.",
        )

        threshold_label = ttk.Label(similarity_filter_frame, text="Umbral de similitud:")
        threshold_label.grid(row=1, column=1, padx=5, pady=2, sticky='w')
        ToolTip(
            threshold_label,
            "Valor entre 0.0 y 1.0. Un valor más alto significa que las preguntas deben ser más idénticas para ser descartadas (0.8 es un buen punto de partida).",
        )

        threshold_spinbox = ttk.Spinbox(
            similarity_filter_frame,
            from_=0.0,
            to=1.0,
            increment=0.05,
            width=6,
            textvariable=self.similarity_threshold_var,
        )
        threshold_spinbox.grid(row=1, column=2, padx=5, pady=2, sticky='w')
        ToolTip(threshold_spinbox, "Ajuste el umbral de similitud. 1.0 significa una coincidencia exacta.")

        # Row 5: Bank Inclusion in Prompt
        prompt_inclusion_frame = ttk.LabelFrame(
            config_frame, text="Inclusión de Banco en Prompt (si se selecciona banco)"
        )
        prompt_inclusion_frame.grid(row=5, column=0, columnspan=3, padx=5, pady=5, sticky='ew')
        ToolTip(
            prompt_inclusion_frame,
            "Define qué preguntas del banco y qué contenido de ellas se incluye en el prompt para guiar la generación.",
        )

        scope_frame = ttk.LabelFrame(
            prompt_inclusion_frame, text="Alcance de Preguntas de para evitar similares en Prompt"
        )
        scope_frame.pack(fill='x', padx=5, pady=(5, 0))

        same_topic_radio = ttk.Radiobutton(
            scope_frame,
            text="Usar preguntas del mismo tema",
            variable=self.bank_in_prompt_scope_var,
            value="mismo_tema",
        )
        same_topic_radio.pack(anchor='w', padx=10, pady=2)
        ToolTip(
            same_topic_radio, "Se usarán como ejemplo preguntas del banco que coincidan con el tema del PDF actual."
        )

        all_topics_radio = ttk.Radiobutton(
            scope_frame,
            text="Usar todas las preguntas del banco",
            variable=self.bank_in_prompt_scope_var,
            value="todos_los_temas",
        )
        all_topics_radio.pack(anchor='w', padx=10, pady=2)
        ToolTip(all_topics_radio, "Se usarán como ejemplo todas las preguntas del banco, independientemente del tema.")

        content_frame = ttk.LabelFrame(
            prompt_inclusion_frame, text="Contenido de Preguntas de para evitar similares en Prompt"
        )
        content_frame.pack(fill='x', padx=5, pady=5)

        enunciados_radio = ttk.Radiobutton(
            content_frame,
            text="Incluir solo enunciados (recomendado)",
            variable=self.prompt_example_content_var,
            value="solo_enunciados",
        )
        enunciados_radio.pack(anchor='w', padx=10, pady=2)
        ToolTip(enunciados_radio, "En el prompt, las preguntas de ejemplo solo mostrarán su enunciado.")

        enunciados_resp_radio = ttk.Radiobutton(
            content_frame,
            text="Incluir enunciados y respuestas",
            variable=self.prompt_example_content_var,
            value="enunciados_y_respuestas",
        )
        enunciados_resp_radio.pack(anchor='w', padx=10, pady=2)
        ToolTip(
            enunciados_resp_radio,
            "En el prompt, las preguntas de ejemplo mostrarán su enunciado y sus opciones de respuesta.",
        )

        include_similar_check = ttk.Checkbutton(
            prompt_inclusion_frame,
            text="Incluir preguntas similares a evitar en prompt",
            variable=self.include_similar_questions_in_prompt_var,
        )
        include_similar_check.pack(anchor='w', padx=10, pady=(0, 5))
        ToolTip(include_similar_check, "Desmarcar para no incluir ejemplos del banco existente dentro del prompt.")

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
        ToolTip(
            save_api_key_button,
            text="Guarda la clave cifrada en el almacén de credenciales del sistema "
            "(en Windows, el Administrador de credenciales).",
        )

        delete_api_key_button = ttk.Button(api_buttons_frame, text="Borrar Clave", command=self.delete_saved_api_key)
        delete_api_key_button.pack(side='left', padx=2)
        ToolTip(
            delete_api_key_button, text="Borra de este equipo la clave guardada (p. ej. en un ordenador compartido)."
        )

        self.load_models_button = ttk.Button(
            api_buttons_frame, text="Cargar Modelos", command=self.populate_models_table
        )
        self.load_models_button.pack(side='left', padx=2)
        ToolTip(self.load_models_button, text="Usa la clave API para obtener la lista de modelos disponibles.")

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
        self.models_tree.column(
            'input_tokens', width=100, stretch=tk.NO, anchor='e'
        )  # 'e' para alinear a la derecha (este)
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

        print_raw_check = ttk.Checkbutton(
            debug_options_frame,
            text="Imprimir respuesta cruda de Gemini (depuración)",
            variable=self.print_raw_gemini_answer_var,
        )
        print_raw_check.pack(anchor='w', padx=5)
        ToolTip(
            print_raw_check,
            "Si se marca, la respuesta completa de la API de Gemini se imprimirá en la consola. Útil para depuración.",
        )

        # Row 8: Output Directory
        output_dir_frame = ttk.LabelFrame(config_frame, text="Directorio de Salida")
        output_dir_frame.grid(row=8, column=0, columnspan=3, padx=5, pady=5, sticky='ew')
        ToolTip(
            output_dir_frame,
            "Carpeta donde se guardarán los archivos generados. Si se deja en blanco, se usará la carpeta actual.",
        )

        output_dir_entry = ttk.Entry(output_dir_frame, textvariable=self.gen_questions_output_dir_var)
        output_dir_entry.pack(side='left', fill='x', expand=True, padx=5, pady=5)
        ToolTip(output_dir_entry, "Ruta al directorio de salida.")

        output_dir_button = ttk.Button(
            output_dir_frame, text="Seleccionar...", command=self.select_gen_questions_output_dir
        )
        output_dir_button.pack(side='left', padx=5, pady=5)
        ToolTip(output_dir_button, "Abrir diálogo para seleccionar el directorio de salida.")

        # Row 9: Generate Button
        self.generate_questions_button = ttk.Button(
            config_frame, text="Generar Preguntas", command=self.generate_questions
        )
        self.generate_questions_button.grid(row=9, column=0, columnspan=3, pady=10)
        ToolTip(
            self.generate_questions_button, "Iniciar el proceso de generación de preguntas con la configuración actual."
        )

        config_frame.columnconfigure(1, weight=1)
        inner_frame_question.columnconfigure(0, weight=1)

        # Bind wheel events after creating all child widgets in this scrollable tab.
        self.app._bind_page_scroll(canvas_question, canvas_question)

    def populate_models_table(self):
        """
        Fetches available Gemini models using the provided API key and populates the Treeview table.
        Adapted for the new google-genai library. The request runs in a background thread so the
        window keeps responding; the table is filled in the main thread.
        """
        api_key = self.api_key_var.get()
        if not api_key or api_key == credentials.PLACEHOLDER:
            messagebox.showerror(
                "Error", "Por favor, introduce una clave API de Gemini válida antes de cargar los modelos."
            )
            return

        # Limpiar la tabla antes de llenarla
        for i in self.models_tree.get_children():
            self.models_tree.delete(i)

        def work():
            # Inicializamos el cliente con la nueva librería
            client = genai.Client(api_key=api_key)

            # Obtenemos el iterador de modelos
            # Nota: La nueva librería maneja la paginación automáticamente
            models_pager = client.models.list()

            rows = []
            for model in models_pager:
                # 1. FILTRO: Solo nos interesan los modelos que se llamen "gemini"
                # Usamos getattr para mayor seguridad por si el objeto cambia
                model_name = getattr(model, 'name', '')
                if 'gemini' not in model_name:
                    continue

                # 2. OBTENCIÓN SEGURA DE DATOS
                # La nueva API puede no devolver todos los campos que tenía la antigua.
                # Usamos getattr(objeto, 'atributo', 'valor_por_defecto') para evitar crashes.

                display_name = getattr(model, 'display_name', model_name)
                version = getattr(model, 'version', '')

                # Los límites de tokens a veces no vienen en el listado general en la nueva API
                input_tokens = getattr(model, 'input_token_limit', 'N/A')
                output_tokens = getattr(model, 'output_token_limit', 'N/A')

                # 'supported_generation_methods' ya no existe en el objeto simple.
                # Asumimos que si es Gemini, soporta generación de contenido.
                methods_str = "generateContent"

                description = getattr(model, 'description', '') or ""
                description = description.replace('\n', ' ')

                rows.append((model_name, display_name, version, input_tokens, output_tokens, methods_str, description))
            return rows

        def on_success(rows):
            # 3. INSERTAR EN LA TABLA (en el hilo principal)
            for values in rows:
                self.models_tree.insert("", "end", values=values)

            if not rows:
                messagebox.showwarning("Sin Modelos", "La API respondió, pero no se encontraron modelos 'gemini'.")

            self.app.update_status(f"Se cargaron {len(rows)} modelos. Por favor, seleccione uno de la tabla.")

        def on_error(e):
            messagebox.showerror(
                "Error de API",
                f"No se pudo obtener la lista de modelos. Verifica tu clave API y conexión a internet.\n\nError: {e}",
            )
            self.app.update_status("Error al cargar modelos.")
            # Imprimimos el error completo en consola para depuración si es necesario
            logger.error(f"Error detallado al cargar modelos: {e}")

        self.app._run_in_background(
            "Cargando lista de modelos...", work, on_success, on_error, widgets=[self.load_models_button]
        )

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
            # El primer valor es el nombre técnico (ej. 'models/gemini-...-flash')
            technical_name = item_values[0]

            self.selected_model_var.set(technical_name)
            self.app.update_status(f"Modelo seleccionado: {technical_name}")

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
            if col_index < 0:
                return

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
                self.tree_tooltip = tw = tk.Toplevel(self.app.root)
                tw.wm_overrideredirect(True)  # Sin bordes ni barra de título

                # Posicionar el tooltip cerca del cursor
                x = self.app.root.winfo_pointerx() + 15
                y = self.app.root.winfo_pointery() + 10
                tw.wm_geometry(f"+{x}+{y}")

                # Añadir una etiqueta con el texto completo
                label = ttk.Label(
                    tw,
                    text=cell_text,
                    justify='left',
                    background="#FFFFE0",
                    relief='solid',
                    borderwidth=1,
                    wraplength=500,
                )  # wraplength para descripciones muy largas
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

    @staticmethod
    def _saved_key_message(saved: credentials.SavedKey) -> str:
        if saved.encrypted:
            message = f"La clave de API se ha guardado cifrada en el {saved.location}."
        else:
            message = (
                "Este sistema no tiene un almacén de credenciales: la clave de API se ha guardado "
                f"sin cifrar en\n{saved.location}\n(solo tu usuario puede leer ese fichero)."
            )
        if os.getenv(credentials.ENV_VAR, "").strip():
            message += (
                "\n\nLa variable de entorno GEMINI_API_KEY está definida y tiene prioridad: "
                "la aplicación la usará mientras exista."
            )
        return message

    def save_current_api_key(self) -> None:
        """
        Saves the API key currently entered in the GUI.

        It goes encrypted to the system credential store (``credentials.save_api_key``); the
        "TU_CLAVE_API" placeholder of the entry is never stored as if it were a key.
        It also shows informational or error messages to the user via messagebox.
        """
        try:
            saved = credentials.save_api_key(self.api_key_var.get())
        except ValueError:
            messagebox.showerror("Error", "Por favor, introduce la API key.")
            return
        # We don't instantiate QuestionGenerator here because it requires a model_name, which might
        # not be selected yet. It will be instantiated when generating questions.
        self.api_key = self.api_key_var.get().strip()
        messagebox.showinfo("Info", self._saved_key_message(saved))

    def delete_saved_api_key(self) -> None:
        """Deletes the key saved with «Guardar Clave» from this computer (e.g. a shared one)."""
        if not messagebox.askyesno("Borrar clave", "¿Borrar de este equipo la clave de API guardada?"):
            return
        if not credentials.delete_api_key():
            messagebox.showinfo("Clave de API", "No había ninguna clave de API guardada en este equipo.")
            return
        self.api_key = credentials.get_api_key()  # GEMINI_API_KEY may still give one
        self.api_key_var.set(self.api_key or credentials.PLACEHOLDER)
        message = "Clave de API borrada de este equipo."
        if self.api_key:
            message += "\n\nLa variable de entorno GEMINI_API_KEY sigue definida y la aplicación la seguirá usando."
        messagebox.showinfo("Clave de API", message)

    def _offer_legacy_key_migration(self) -> None:
        """SEC-3: older versions saved the key unencrypted in ``config.json`` of the current folder.

        Offers to move it to the credential store (or, if a key is already saved there, to delete
        that copy). If the user declines, the key is still used in this session, as before.
        """
        legacy = credentials.find_legacy_api_key()
        if legacy is None:
            return
        path, legacy_key = legacy
        already_saved = credentials.get_saved_api_key() is not None
        question = f"Hay una clave de API guardada sin cifrar, por una versión anterior, en:\n{path}\n\n" + (
            "Ya tienes una clave guardada en el almacén de credenciales. ¿Borrar esa copia sin cifrar?"
            if already_saved
            else "¿Moverla al almacén de credenciales del sistema (cifrada) y borrar ese fichero?"
        )
        if not messagebox.askyesno("Clave de API sin cifrar", question):
            if not self.api_key:
                self.api_key = legacy_key
                self.api_key_var.set(legacy_key)
            return
        try:
            saved = None if already_saved else credentials.save_api_key(legacy_key)
            credentials.remove_legacy_api_key(path)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Error", f"No se pudo terminar de mover la clave de API:\n{exc}")
            return
        if saved is not None:
            if not self.api_key:
                self.api_key = legacy_key
                self.api_key_var.set(legacy_key)
            messagebox.showinfo("Clave de API", f"{self._saved_key_message(saved)}\n\nSe ha borrado {path}.")
        else:
            messagebox.showinfo("Clave de API", f"Se ha borrado la copia sin cifrar:\n{path}")

    def select_pdf_files(self) -> None:
        """
        Opens a dialog for the user to select one or more source files.
        The paths of the selected files are inserted into the corresponding entry widget.
        """
        file_paths = filedialog.askopenfilenames(
            title="Seleccionar archivos fuente",
            filetypes=(
                ("Archivos soportados", "*.pdf *.png *.jpg *.jpeg *.webp *.bmp *.gif *.tif *.tiff"),
                ("Archivos PDF", "*.pdf"),
                ("Imágenes", "*.png *.jpg *.jpeg *.webp *.bmp *.gif *.tif *.tiff"),
                ("Todos los archivos", "*.*"),
            ),
        )
        if not file_paths:
            return  # Dialog cancelled: keep the current list.
        # Add to the current list (no duplicates) with ';' as separator: before, a second selection
        # was glued to the first one without any separator ('a.pdfb.pdf').
        paths = gui_logic.split_paths(self.pdf_files_var.get())
        paths += [p for p in file_paths if p not in paths]
        self.pdf_files_var.set(";".join(paths))

    def select_existing_bank_for_gen_file(self) -> None:
        """
        Opens a dialog for the user to select an existing Excel file
        to use as a question bank when generating new questions (optional).
        The path of the selected file is saved in the `self.existing_bank_for_gen_path` variable.
        """
        filepath = filedialog.askopenfilename(
            title="Seleccionar Banco de Preguntas Existente (Opcional)", filetypes=[("Archivos Excel", "*.xlsx;*.xls")]
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
        pdf_paths = gui_logic.split_paths(pdf_paths_str)
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

        # Empty name: the library default ('preguntas').
        output_filename = self.output_filename_var.get().strip() or None

        # Obtenemos el modelo directamente de la variable que se actualiza con la tabla
        technical_model_name = self.selected_model_var.get()
        if not technical_model_name:
            messagebox.showerror("Error", "Por favor, carga y selecciona un modelo de la tabla.")
            return

        if not api_key or api_key == credentials.PLACEHOLDER:
            messagebox.showerror("Error", "Por favor, introduce tu clave API de Gemini.")
            return
        if not pdf_paths:
            messagebox.showerror("Error", "Por favor, selecciona al menos un archivo PDF.")
            return

        if self.input_mode_var.get() == "text":
            non_pdf_paths = [path for path in pdf_paths if not path.lower().endswith('.pdf')]
            if non_pdf_paths:
                messagebox.showerror("Error", "En modo 'text' solo se permiten archivos PDF.")
                return

        try:
            # Re-initialize the generator with the current model and API key.
            # This is important if the user changes the model or API key.
            self.question_generator = QuestionGenerator(api_key, model_name=technical_model_name)
        except Exception as e:
            messagebox.showerror("Error", f"Error al inicializar el generador de preguntas: {e}")
            return

        existing_bank_path_for_gen = self.existing_bank_for_gen_path.get()
        bank_prompt_scope_value = self.bank_in_prompt_scope_var.get()
        prompt_example_content_value = self.prompt_example_content_var.get()
        input_mode_value = self.input_mode_var.get() or "text"
        print_raw_gemini_answer_value = self.print_raw_gemini_answer_var.get()  # Get checkbox value.

        similarity_threshold_value = None
        if self.use_similarity_filter_var.get() and existing_bank_path_for_gen:
            try:
                similarity_threshold_value = float(self.similarity_threshold_var.get())
                if not (0.0 <= similarity_threshold_value <= 1.0):
                    messagebox.showerror("Error", "El umbral de similitud debe estar entre 0.0 y 1.0.")
                    self.app.update_status("Error en el umbral de similitud.")
                    return
            except ValueError:
                messagebox.showerror("Error", "El umbral de similitud debe ser un número.")
                self.app.update_status("Error en el umbral de similitud.")
                return

        process_by_pages_value = self.process_by_pages_var.get()
        pages_per_chunk_value = 1  # Default value if not processing by pages.
        total_chunks_value = None
        chunking_mode_value = self.chunking_mode_var.get() or "pages"
        if process_by_pages_value:
            try:
                pages_per_chunk_value = int(self.pages_per_chunk_var.get())
                if pages_per_chunk_value <= 0:
                    messagebox.showerror("Error", "Las páginas por fragmento deben ser un entero positivo.")
                    self.app.update_status("Error en páginas por fragmento.")
                    return
            except ValueError:
                messagebox.showerror("Error", "Las páginas por fragmento deben ser un número entero.")
                self.app.update_status("Error en páginas por fragmento.")
                return

            total_chunks_raw = self.total_chunks_var.get().strip()
            if total_chunks_raw:
                try:
                    total_chunks_value = int(total_chunks_raw)
                    if total_chunks_value <= 0:
                        messagebox.showerror("Error", "El número total de fragmentos debe ser un entero positivo.")
                        return
                except ValueError:
                    messagebox.showerror("Error", "El número total de fragmentos debe ser un número entero.")
                    return

        bank_prompt_scope_to_pass = bank_prompt_scope_value if existing_bank_path_for_gen else None

        output_dir_value = self.gen_questions_output_dir_var.get() or None
        include_similar_questions_value = self.include_similar_questions_in_prompt_var.get()
        generator = self.question_generator

        # The calls to Gemini can take minutes: they run in a worker thread (no Tk access there).
        def work():
            return generator.generate_multiple_choice_questions(
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
                max_generation_attempts_per_chunk=max_attempts_value,
                total_chunks=total_chunks_value,
                chunking_mode=chunking_mode_value,
                include_similar_questions_in_prompt=include_similar_questions_value,
                input_mode=input_mode_value,
            )

        def on_success(questions_df):
            if questions_df is not None and not questions_df.empty:
                self.app.update_status(f"Preguntas generadas y guardadas ({len(questions_df)} en total).")
                messagebox.showinfo("Éxito", f"Preguntas generadas y guardadas ({len(questions_df)} en total).")
            else:
                # This message may appear if, after all attempts and filters, no questions are left.
                self.app.update_status("No se generaron preguntas o ninguna pasó los filtros.")
                messagebox.showinfo(
                    "Resultado",
                    "No se generaron preguntas o ninguna pasó los filtros (ej. similitud, errores de API). Revisa la consola para más detalles.",
                )

        def on_error(e):
            if isinstance(e, QuotaExceededError):
                title = "Límite de Cuota Excedido"
                # El mensaje 'e' ya viene formateado desde QuestionGenerator
                message = str(e)

                self.app.update_status("Error: Límite de cuota de la API excedido.")
                messagebox.showerror(title, message)
                logger.error(f"ERROR: {title}\n{message}")
            elif isinstance(e, ServiceOverloadedError):
                title = "Servidores de Google Saturados"
                self.app.update_status("Error: Modelo de IA saturado.")
                messagebox.showwarning(title, str(e))  # Usamos warning porque es temporal
                logger.error(f"ERROR: {title}\n{e}")
            elif isinstance(e, GeminiRequestError):
                # Invalid key or retired model: the message says what to change.
                self.app.update_status("Error: la API de Gemini ha rechazado la petición.")
                messagebox.showerror("Error de la API de Gemini", str(e))
            else:
                self.app.update_status(f"Error durante la generación de preguntas: {e}")
                messagebox.showerror("Error", f"Error: {e}")
                import traceback

                logger.error("".join(traceback.format_exception(type(e), e, e.__traceback__)))

        self.app._run_in_background(
            "Generando preguntas...", work, on_success, on_error, widgets=[self.generate_questions_button]
        )

    def select_gen_questions_output_dir(self) -> None:
        """Opens a dialog to select the output directory for generated questions."""
        directory = filedialog.askdirectory(title="Seleccionar Directorio de Salida para Preguntas Generadas")
        if directory:
            self.gen_questions_output_dir_var.set(directory)
