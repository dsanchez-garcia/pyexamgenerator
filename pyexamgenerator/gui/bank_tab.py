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

"""The «Gestionar Banco de Preguntas» tab (ARC-1): XLSX from the reviewed DOCX, adding reviewed
questions to a bank, recording the usage of the generated exams and unifying banks.
"""

import os
import tkinter as tk
from tkinter import filedialog, simpledialog, ttk
from typing import Dict, List, Optional


from pyexamgenerator import schema
from pyexamgenerator.gui._dialogs import messagebox
from pyexamgenerator.question_bank_manager import QuestionBankManager
from pyexamgenerator.tooltip import ToolTip


class BankTab:
    """Widgets, variables and actions of the «Gestionar Banco de Preguntas» tab.

    ``app`` is the :class:`~pyexamgenerator.main_app.ExamApp` that owns the window: the tab uses its
    notebook, status bar and page-scroll helpers.
    """

    def __init__(self, app) -> None:
        self.app = app
        self.question_bank_manager = QuestionBankManager()
        self.existing_bank_path = tk.StringVar()
        self.reviewed_add_path = tk.StringVar()
        self.add_questions_filter_var = tk.StringVar(value="todas")
        self.duplicate_check_var = tk.StringVar(value="pregunta_unica")
        self.update_bank_path_var = tk.StringVar()
        # Lista de exámenes con los que actualizar el banco; cada entrada es {"path", "label"}.
        self.update_exam_specs: List[Dict[str, str]] = []
        # Configuración para derivar la etiqueta a partir del nombre del archivo del examen.
        self.update_label_delimiter_var = tk.StringVar(value="_")
        self.update_label_parts_var = tk.StringVar(value="")
        self.revised_xlsx_output_dir_var = tk.StringVar()
        self.revised_docx_path_var = tk.StringVar()
        self.new_xlsx_filename_var = tk.StringVar()
        # Unificación de varios bancos en uno definitivo.
        self.unify_duplicate_check_var = tk.StringVar(value="pregunta_respuestas")
        self.unify_banks_display_var = tk.StringVar(value="")
        self.unify_bank_paths: list = []

        self.create_manage_bank_tab()

    def create_manage_bank_tab(self):
        """
        Creates the 'Manage Question Bank' tab with all its widgets.
        """
        canvas_manage, inner_frame_manage = self.app._create_scrollable_tab(
            'Gestionar Banco de Preguntas', fill_width=True
        )

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
        ToolTip(
            xlsx_output_dir_label,
            "Carpeta donde se guardará el nuevo archivo XLSX. Si se deja en blanco, se usará la misma carpeta que el DOCX de entrada.",
        )

        xlsx_output_dir_entry = ttk.Entry(docx_xlsx_group, width=50, textvariable=self.revised_xlsx_output_dir_var)
        xlsx_output_dir_entry.grid(row=1, column=1, padx=5, pady=5, sticky='ew')
        ToolTip(xlsx_output_dir_entry, "Ruta al directorio de salida para el archivo XLSX.")

        xlsx_output_dir_button = ttk.Button(
            docx_xlsx_group, text="Seleccionar...", command=self.select_revised_xlsx_output_dir
        )
        xlsx_output_dir_button.grid(row=1, column=2, padx=5, pady=5)
        ToolTip(xlsx_output_dir_button, "Abrir diálogo para seleccionar el directorio de salida.")

        # CAMBIO: Se ajusta la fila del nombre del archivo a la 2.
        xlsx_label = ttk.Label(docx_xlsx_group, text="Nombre del Nuevo Archivo XLSX:")
        xlsx_label.grid(row=2, column=0, padx=5, pady=5, sticky='w')
        ToolTip(
            xlsx_label,
            text="Ingrese el nombre para el nuevo archivo XLSX donde se guardarán las preguntas revisadas. Si se deja vacío, se usará el nombre del DOCX.",
        )

        new_xlsx_entry = ttk.Entry(docx_xlsx_group, width=50, textvariable=self.new_xlsx_filename_var)
        new_xlsx_entry.grid(row=2, column=1, padx=5, pady=5, sticky='ew')
        ToolTip(new_xlsx_entry, text="Nombre del archivo XLSX de salida.")
        xlsx_button = ttk.Button(
            docx_xlsx_group, text="Guardar XLSX Revisado", command=self.save_revised_questions_to_xlsx
        )
        xlsx_button.grid(row=2, column=2, padx=5, pady=5)
        ToolTip(xlsx_button, text="Guarda las preguntas revisadas en un nuevo archivo XLSX.")

        docx_xlsx_group.columnconfigure(1, weight=1)

        # --- Section to add questions from another bank ---
        add_from_bank_frame = ttk.LabelFrame(inner_frame_manage, text="Añadir Preguntas Existentes")
        add_from_bank_frame.pack(padx=5, pady=10, fill='x')

        existing_bank_label = ttk.Label(add_from_bank_frame, text="Banco Existente:")
        existing_bank_label.grid(row=0, column=0, padx=5, pady=5, sticky='w')
        ToolTip(
            existing_bank_label,
            text="Seleccione el archivo XLSX del banco de preguntas existente al que se añadirán las nuevas preguntas.",
        )

        existing_bank_entry = ttk.Entry(add_from_bank_frame, width=40, textvariable=self.existing_bank_path)
        existing_bank_entry.grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        ToolTip(existing_bank_entry, text="Ruta del archivo XLSX del banco de preguntas existente.")

        select_existing_button = ttk.Button(
            add_from_bank_frame, text="Seleccionar", command=self.select_existing_bank_file
        )
        select_existing_button.grid(row=0, column=2, padx=5, pady=5)
        ToolTip(
            select_existing_button,
            text="Abre un diálogo para seleccionar el archivo XLSX del banco de preguntas existente.",
        )

        reviewed_add_label = ttk.Label(add_from_bank_frame, text="Archivo a Añadir:")
        reviewed_add_label.grid(row=1, column=0, padx=5, pady=5, sticky='w')
        ToolTip(
            reviewed_add_label,
            text="Seleccione el archivo XLSX que contiene las preguntas que desea añadir al banco existente.",
        )

        reviewed_add_entry = ttk.Entry(add_from_bank_frame, width=40, textvariable=self.reviewed_add_path)
        reviewed_add_entry.grid(row=1, column=1, padx=5, pady=5, sticky='ew')
        ToolTip(reviewed_add_entry, text="Ruta del archivo XLSX con las preguntas a añadir.")

        select_add_button = ttk.Button(
            add_from_bank_frame, text="Seleccionar", command=self.select_reviewed_file_to_add
        )
        select_add_button.grid(row=1, column=2, padx=5, pady=5)
        ToolTip(select_add_button, text="Abre un diálogo para seleccionar el archivo XLSX con las preguntas a añadir.")

        duplicate_criteria_frame = ttk.LabelFrame(add_from_bank_frame, text="Criterio de Duplicado")
        duplicate_criteria_frame.grid(row=2, column=0, columnspan=3, padx=5, pady=5, sticky='ew')
        ToolTip(
            duplicate_criteria_frame,
            text="Seleccione el criterio para determinar si una pregunta ya existe en el banco de preguntas.",
        )

        check_pregunta_unica = ttk.Radiobutton(
            duplicate_criteria_frame,
            text="Pregunta Única (ignorar respuestas)",
            variable=self.duplicate_check_var,
            value="pregunta_unica",
        )
        check_pregunta_unica.pack(side='left', padx=10)
        ToolTip(
            check_pregunta_unica,
            text="Solo se compara el texto de la pregunta para detectar duplicados. Las respuestas no se tienen en cuenta. Solo se añade si la pregunta es diferente.",
        )

        check_pregunta_respuestas = ttk.Radiobutton(
            duplicate_criteria_frame,
            text="Pregunta y Respuestas Iguales",
            variable=self.duplicate_check_var,
            value="pregunta_respuestas",
        )
        check_pregunta_respuestas.pack(side='left', padx=10)
        ToolTip(
            check_pregunta_respuestas,
            text="Se compara el texto de la pregunta y todas las opciones de respuesta para detectar duplicados. Solo se añade si la pregunta o alguna de sus respuestas son diferentes.",
        )

        filter_state_frame = ttk.LabelFrame(add_from_bank_frame, text="Filtro de Estado")
        filter_state_frame.grid(row=3, column=0, columnspan=3, padx=5, pady=5, sticky='ew')
        ToolTip(
            filter_state_frame,
            text="Elija si desea añadir todas las preguntas del archivo o solo las que están marcadas como 'Aceptable'.",
        )

        add_all_radio = ttk.Radiobutton(
            filter_state_frame, text="Añadir todas las preguntas", variable=self.add_questions_filter_var, value="todas"
        )
        add_all_radio.pack(side='left', padx=10)
        ToolTip(
            add_all_radio,
            text="Se intentarán añadir todas las preguntas del archivo de origen, sin importar su estado.",
        )

        add_acceptable_radio = ttk.Radiobutton(
            filter_state_frame,
            text="Añadir solo con estado 'Aceptable'",
            variable=self.add_questions_filter_var,
            value="aceptable",
        )
        add_acceptable_radio.pack(side='left', padx=10)
        ToolTip(
            add_acceptable_radio,
            text="Solo se añadirán las preguntas del archivo de origen que tengan 'Aceptable' en la columna 'Estado'.",
        )

        add_button = ttk.Button(
            add_from_bank_frame, text="Añadir Preguntas sin Duplicados", command=self.add_reviewed_questions_to_bank
        )
        add_button.grid(row=4, column=0, columnspan=3, pady=10)
        ToolTip(
            add_button,
            text="Inicia el proceso de añadir las preguntas del archivo seleccionado al banco existente, evitando duplicados según el criterio elegido.",
        )

        add_from_bank_frame.columnconfigure(1, weight=1)

        # --- Section to update the bank usage statistics from one or more already generated exams ---
        update_with_exam_frame = ttk.LabelFrame(inner_frame_manage, text="Actualizar Banco con Exámenes Existentes")
        update_with_exam_frame.pack(padx=5, pady=10, fill='x')
        ToolTip(
            update_with_exam_frame,
            text="Marca como usadas en el banco las preguntas que aparecen en uno o varios exámenes ya generados (cada uno con su etiqueta) y recalcula 'Veces usada en examen'.",
        )

        update_bank_label = ttk.Label(update_with_exam_frame, text="Banco a Actualizar:")
        update_bank_label.grid(row=0, column=0, padx=5, pady=5, sticky='w')
        ToolTip(
            update_bank_label,
            text="Seleccione el archivo XLSX del banco de preguntas cuyas estadísticas de uso se actualizarán.",
        )

        update_bank_entry = ttk.Entry(update_with_exam_frame, width=40, textvariable=self.update_bank_path_var)
        update_bank_entry.grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        ToolTip(update_bank_entry, text="Ruta del archivo XLSX del banco de preguntas.")

        select_update_bank_button = ttk.Button(
            update_with_exam_frame, text="Seleccionar", command=self.select_update_bank_file
        )
        select_update_bank_button.grid(row=0, column=2, padx=5, pady=5)
        ToolTip(
            select_update_bank_button, text="Abre un diálogo para seleccionar el archivo XLSX del banco de preguntas."
        )

        update_exams_label = ttk.Label(update_with_exam_frame, text="Exámenes a registrar:")
        update_exams_label.grid(row=1, column=0, padx=5, pady=5, sticky='nw')
        ToolTip(
            update_exams_label,
            text="Lista de exámenes ya generados (normalmente los archivos '..._completo.xlsx'). Cada uno se registra con su propia etiqueta en una columna '<etiqueta>_uso'.",
        )

        # Tabla con los exámenes seleccionados, su etiqueta y la columna de uso resultante.
        exams_tree_frame = ttk.Frame(update_with_exam_frame)
        exams_tree_frame.grid(row=1, column=1, padx=5, pady=5, sticky='ew')
        self.update_exams_tree = ttk.Treeview(
            exams_tree_frame, columns=('examen', 'etiqueta', 'columna'), show='headings', height=4
        )
        self.update_exams_tree.heading('examen', text='Examen (XLSX)')
        self.update_exams_tree.heading('etiqueta', text='Etiqueta')
        self.update_exams_tree.heading('columna', text='Columna en XLSX')
        self.update_exams_tree.column('examen', width=220)
        self.update_exams_tree.column('etiqueta', width=150)
        self.update_exams_tree.column('columna', width=170)
        self.update_exams_tree.grid(row=0, column=0, sticky='ew')
        exams_tree_scroll = ttk.Scrollbar(exams_tree_frame, orient='vertical', command=self.update_exams_tree.yview)
        self.update_exams_tree.configure(yscrollcommand=exams_tree_scroll.set)
        exams_tree_scroll.grid(row=0, column=1, sticky='ns')
        exams_tree_frame.columnconfigure(0, weight=1)
        # Doble clic sobre una fila para editar su etiqueta.
        self.update_exams_tree.bind('<Double-1>', self._on_update_exam_double_click)
        ToolTip(
            self.update_exams_tree,
            text="Exámenes seleccionados, su etiqueta y la columna que se escribirá en el XLSX (sin tildes ni caracteres especiales). Haga doble clic en una fila para editar la etiqueta.",
        )

        exams_buttons_frame = ttk.Frame(update_with_exam_frame)
        exams_buttons_frame.grid(row=1, column=2, padx=5, pady=5, sticky='n')

        add_exam_button = ttk.Button(exams_buttons_frame, text="Añadir...", command=self.select_update_exam_files)
        add_exam_button.pack(fill='x', pady=2)
        ToolTip(
            add_exam_button,
            text="Abre un diálogo para añadir uno o varios archivos XLSX de examen. La etiqueta inicial se deriva del nombre del archivo según la configuración de 'Etiqueta automática'.",
        )

        edit_label_button = ttk.Button(exams_buttons_frame, text="Editar etiqueta", command=self.edit_update_exam_label)
        edit_label_button.pack(fill='x', pady=2)
        ToolTip(edit_label_button, text="Edita la etiqueta del examen seleccionado (nombre de la columna de uso).")

        remove_exam_button = ttk.Button(exams_buttons_frame, text="Quitar", command=self.remove_update_exam)
        remove_exam_button.pack(fill='x', pady=2)
        ToolTip(remove_exam_button, text="Quita de la lista el examen seleccionado.")

        clear_exams_button = ttk.Button(exams_buttons_frame, text="Limpiar", command=self.clear_update_exams)
        clear_exams_button.pack(fill='x', pady=2)
        ToolTip(clear_exams_button, text="Vacía la lista de exámenes.")

        # --- Sub-sección: etiqueta automática derivada del nombre del archivo ---
        auto_label_frame = ttk.LabelFrame(
            update_with_exam_frame, text="Etiqueta automática (desde el nombre del archivo)"
        )
        auto_label_frame.grid(row=2, column=0, columnspan=3, padx=5, pady=5, sticky='ew')
        ToolTip(
            auto_label_frame,
            text="Deriva la etiqueta partiendo el nombre del archivo por un delimitador y quedándote con las partes elegidas. Las tildes se eliminan al escribir la columna.",
        )

        delimiter_label = ttk.Label(auto_label_frame, text="Delimitador:")
        delimiter_label.grid(row=0, column=0, padx=5, pady=5, sticky='w')
        delimiter_entry = ttk.Entry(auto_label_frame, width=6, textvariable=self.update_label_delimiter_var)
        delimiter_entry.grid(row=0, column=1, padx=5, pady=5, sticky='w')
        ToolTip(delimiter_entry, text="Carácter por el que se parte el nombre del archivo (por defecto '_').")

        parts_label = ttk.Label(auto_label_frame, text="Partes a conservar:")
        parts_label.grid(row=0, column=2, padx=5, pady=5, sticky='w')
        parts_entry = ttk.Entry(auto_label_frame, width=20, textvariable=self.update_label_parts_var)
        parts_entry.grid(row=0, column=3, padx=5, pady=5, sticky='ew')
        ToolTip(
            parts_entry,
            text=(
                "Índices (1 = primera parte) separados por comas; admite rangos 'a:b' (inclusive) e índices "
                "negativos contados desde el final (-1 = última). Ejemplo: '2:3, -4:-2'. "
                "Vacío = se usa el nombre completo del archivo."
            ),
        )

        apply_label_button = ttk.Button(auto_label_frame, text="Aplicar a la lista", command=self.apply_auto_labels)
        apply_label_button.grid(row=0, column=4, padx=5, pady=5, sticky='e')
        ToolTip(
            apply_label_button,
            text="Recalcula la etiqueta de todos los exámenes de la lista con el delimitador y las partes indicados.",
        )

        auto_label_frame.columnconfigure(3, weight=1)

        update_bank_button = ttk.Button(
            update_with_exam_frame, text="Actualizar Banco con Exámenes", command=self.update_bank_with_exams_action
        )
        update_bank_button.grid(row=3, column=0, columnspan=3, pady=10)
        ToolTip(
            update_bank_button,
            text="Empareja por enunciado las preguntas de cada examen con el banco, marca su uso en una columna por etiqueta y recalcula 'Veces usada en examen'.",
        )

        update_with_exam_frame.columnconfigure(1, weight=1)

        # --- Section to unify several banks into one definitive bank ---
        unify_frame = ttk.LabelFrame(inner_frame_manage, text="Unificar Bancos de Preguntas")
        unify_frame.pack(padx=5, pady=10, fill='x')
        ToolTip(
            unify_frame,
            text="Combina varios bancos en uno solo, eliminando duplicados según el criterio elegido. El primer banco tiene prioridad cuando una pregunta aparece en varios.",
        )

        unify_banks_label = ttk.Label(unify_frame, text="Bancos a Unificar:")
        unify_banks_label.grid(row=0, column=0, padx=5, pady=5, sticky='w')
        ToolTip(unify_banks_label, text="Seleccione dos o más archivos XLSX de bancos de preguntas a combinar.")

        unify_banks_entry = ttk.Entry(
            unify_frame, width=40, textvariable=self.unify_banks_display_var, state='readonly'
        )
        unify_banks_entry.grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        ToolTip(unify_banks_entry, text="Archivos de bancos seleccionados (en orden de prioridad).")

        select_unify_button = ttk.Button(unify_frame, text="Seleccionar...", command=self.select_unify_bank_files)
        select_unify_button.grid(row=0, column=2, padx=5, pady=5)
        ToolTip(select_unify_button, text="Abre un diálogo para seleccionar varios archivos XLSX de bancos a unificar.")

        unify_criteria_frame = ttk.LabelFrame(unify_frame, text="Criterio de Duplicado")
        unify_criteria_frame.grid(row=1, column=0, columnspan=3, padx=5, pady=5, sticky='ew')
        ToolTip(unify_criteria_frame, text="Seleccione cómo decidir si dos preguntas de bancos distintos son la misma.")

        unify_statement_radio = ttk.Radiobutton(
            unify_criteria_frame, text="Solo enunciado", variable=self.unify_duplicate_check_var, value="pregunta_unica"
        )
        unify_statement_radio.pack(side='left', padx=10)
        ToolTip(
            unify_statement_radio,
            text="Si el enunciado coincide se considera la misma pregunta (se conserva una). Las respuestas no se tienen en cuenta.",
        )

        unify_full_radio = ttk.Radiobutton(
            unify_criteria_frame,
            text="Enunciado y respuestas",
            variable=self.unify_duplicate_check_var,
            value="pregunta_respuestas",
        )
        unify_full_radio.pack(side='left', padx=10)
        ToolTip(
            unify_full_radio,
            text="Solo es duplicado si coinciden el enunciado y el conjunto de respuestas (sin importar el orden). Mismo enunciado con respuestas distintas se conservan como preguntas diferentes.",
        )

        unify_button = ttk.Button(unify_frame, text="Unificar Bancos", command=self.unify_question_banks_action)
        unify_button.grid(row=2, column=0, columnspan=3, pady=10)
        ToolTip(
            unify_button, text="Combina los bancos seleccionados en uno solo sin duplicados y pregunta dónde guardarlo."
        )

        unify_frame.columnconfigure(1, weight=1)

        # Mouse wheel support (Windows/macOS + Linux) across the whole widget tree, bound after
        # creating all child widgets in the scrollable frame.
        self.app._bind_page_scroll(canvas_manage, canvas_manage)

    def select_unify_bank_files(self) -> None:
        """Opens a dialog to select several question bank XLSX files to unify."""
        filepaths = filedialog.askopenfilenames(
            title="Seleccionar Bancos de Preguntas a Unificar", filetypes=[("Archivos Excel", "*.xlsx")]
        )
        if filepaths:
            self.unify_bank_paths = list(filepaths)
            names = ", ".join(os.path.basename(p) for p in self.unify_bank_paths)
            self.unify_banks_display_var.set(f"{len(self.unify_bank_paths)} bancos: {names}")

    def unify_question_banks_action(self) -> None:
        """Unifies the selected question banks into one, removing duplicates by the chosen criterion."""
        if len(self.unify_bank_paths) < 2:
            messagebox.showerror("Error", "Seleccione al menos dos bancos de preguntas para unificar.")
            return

        criterion = self.unify_duplicate_check_var.get()
        try:
            unified_df, stats = self.question_bank_manager.unify_question_banks(
                self.unify_bank_paths,
                output_path=None,
                duplicate_criterion=criterion,
                save=False,
            )
        except Exception as e:  # noqa: BLE001 - surface any error to the user.
            messagebox.showerror("Error", f"No se pudieron unificar los bancos:\n{e}")
            return

        if unified_df is None:
            messagebox.showerror("Error", "No se pudo leer ningún banco. Revise la consola para más detalles.")
            return

        save_path = filedialog.asksaveasfilename(
            title="Guardar Banco Unificado Como...",
            defaultextension=".xlsx",
            initialdir=os.path.dirname(self.unify_bank_paths[0]),
            initialfile="banco_unificado.xlsx",
            filetypes=[("Archivos Excel", "*.xlsx")],
        )
        if not save_path:
            return

        filepath = self.question_bank_manager.save_dataframe_to_excel(unified_df, save_path, overwrite=True)
        if filepath:
            errors = stats.get("errors", [])
            extra = f"\nBancos no leídos: {len(errors)}" if errors else ""
            messagebox.showinfo(
                "Éxito",
                f"Banco unificado guardado en: {filepath}\n"
                f"Preguntas únicas: {stats['unified']}\n"
                f"Duplicados eliminados: {stats['duplicates_removed']} "
                f"(de {stats['total_read']} leídas){extra}",
            )
        else:
            messagebox.showerror("Error al guardar", "Error al guardar el banco unificado.")

    def select_revised_docx_file(self) -> None:
        """
        Opens a dialog to select a revised DOCX file.
        The path of the selected file is saved in the `self.revised_docx_path_var` variable.
        """
        filepath = filedialog.askopenfilename(
            title="Seleccionar Archivo DOCX Revisado", filetypes=[("Archivos Word", "*.docx")]
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
            docx_path=revised_docx_path, excel_output_filename=new_xlsx_filename, output_dir=output_dir_value
        )

        if saved_path:
            messagebox.showinfo("Guardado", f"Las preguntas revisadas se han guardado en: {saved_path}")
        else:
            messagebox.showerror(
                "Error al Guardar", "Ocurrió un error al generar el archivo XLSX. Revise la consola para más detalles."
            )

    def select_existing_bank_file(self) -> None:
        """
        Opens a dialog for the user to select an existing Excel file
        that contains the question bank.
        The path of the selected file is saved in the `self.existing_bank_path` variable.
        """
        filepath = filedialog.askopenfilename(
            title="Seleccionar Archivo Excel Existente", filetypes=[("Archivos Excel", "*.xlsx;*.xls")]
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
            title="Seleccionar Archivo Excel Revisado", filetypes=[("Archivos Excel", "*.xlsx;*.xls")]
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
        duplicate_check_columns = [schema.QUESTION]  # Default criteria.

        if duplicate_criteria == "pregunta_respuestas":
            duplicate_check_columns = [schema.QUESTION, *schema.ANSWER_COLUMNS]

        if not existing_bank_path or not reviewed_add_path:
            messagebox.showerror("Error", "Por favor, seleccione ambos archivos.")
            return

        # Determine the boolean value from user selection.
        only_acceptable = self.add_questions_filter_var.get() == "aceptable"

        # Pass the new boolean argument to the backend method.
        added_count, df_updated = self.question_bank_manager.add_questions_without_duplicates(
            existing_bank_path,
            reviewed_add_path,
            duplicate_check_columns=duplicate_check_columns,
            add_only_acceptable=only_acceptable,
        )

        if added_count == -1 or df_updated is None:
            messagebox.showerror("Error", "Error al procesar los archivos.")
            return

        if added_count > 0:
            response = messagebox.askyesnocancel(
                "Guardar Cambios",
                f"Se añadieron {added_count} preguntas nuevas. ¿Desea guardar los cambios en el archivo existente?",
                default='yes',
            )
            if response is True:
                filepath = self.question_bank_manager.save_dataframe_to_excel(
                    df_updated, existing_bank_path, overwrite=True
                )
                if filepath:
                    messagebox.showinfo(
                        "Éxito", f"Se añadieron {added_count} preguntas al archivo existente: {filepath}"
                    )
                else:
                    messagebox.showerror("Error al guardar", "Error al guardar el archivo existente.")
            elif response is False:
                new_filepath = filedialog.asksaveasfilename(
                    title="Guardar Banco de Preguntas Actualizado Como...",
                    defaultextension=".xlsx",
                    initialdir=os.path.dirname(existing_bank_path),
                    initialfile=f"{os.path.splitext(os.path.basename(existing_bank_path))[0]}_actualizado.xlsx",
                )
                if new_filepath:
                    filepath = self.question_bank_manager.save_dataframe_to_excel(
                        df_updated, new_filepath, overwrite=True
                    )
                    if filepath:
                        messagebox.showinfo("Éxito", f"Se guardaron {added_count} preguntas en: {filepath}")
                    else:
                        messagebox.showerror("Error al guardar", "Error al guardar el nuevo archivo.")
        else:
            messagebox.showinfo("Información", "No se encontraron preguntas nuevas para añadir.")

    def select_update_bank_file(self) -> None:
        """Opens a dialog to select the question bank XLSX whose usage will be updated."""
        filepath = filedialog.askopenfilename(
            title="Seleccionar Banco de Preguntas a Actualizar", filetypes=[("Archivos Excel", "*.xlsx;*.xls")]
        )
        if filepath:
            self.update_bank_path_var.set(filepath)

    def _default_exam_label(self, exam_path: str) -> str:
        """Default label for an exam, derived from its file name using the auto-label settings.

        Splits the file name by the configured delimiter and keeps the chosen parts. With the parts
        field empty it returns the whole file name (without extension).
        """
        delimiter = self.update_label_delimiter_var.get()
        parts = self.update_label_parts_var.get().strip()
        return self.question_bank_manager.label_from_filename(
            exam_path,
            delimiter=delimiter or None,
            parts=parts or None,
        )

    def _refresh_update_exams_tree(self) -> None:
        """Repopulates the exams Treeview from ``self.update_exam_specs`` (index used as item id).

        Also shows the resulting usage column name (accents stripped) so the user sees exactly what
        will be written to the bank XLSX.
        """
        self.update_exams_tree.delete(*self.update_exams_tree.get_children())
        for index, spec in enumerate(self.update_exam_specs):
            column_name = self.question_bank_manager.usage_column_name(spec["label"], spec["path"])
            self.update_exams_tree.insert(
                "", "end", iid=str(index), values=(os.path.basename(spec["path"]), spec["label"], column_name)
            )

    def apply_auto_labels(self) -> None:
        """Recomputes the label of every exam in the list from its file name using the auto-label settings."""
        if not self.update_exam_specs:
            messagebox.showinfo("Información", "No hay exámenes en la lista a los que aplicar la etiqueta.")
            return
        for spec in self.update_exam_specs:
            spec["label"] = self._default_exam_label(spec["path"])
        self._refresh_update_exams_tree()

    def select_update_exam_files(self) -> None:
        """Opens a dialog to add one or more generated exam XLSX files used to update the bank.

        Each newly added exam gets a default label (its file name without extension), editable later.
        Files already present in the list are not added twice.
        """
        filepaths = filedialog.askopenfilenames(
            title="Seleccionar Exámenes Generados (XLSX)", filetypes=[("Archivos Excel", "*.xlsx;*.xls")]
        )
        if not filepaths:
            return
        existing_paths = {spec["path"] for spec in self.update_exam_specs}
        for filepath in filepaths:
            if filepath in existing_paths:
                continue
            self.update_exam_specs.append({"path": filepath, "label": self._default_exam_label(filepath)})
            existing_paths.add(filepath)
        self._refresh_update_exams_tree()

    def _selected_update_exam_index(self) -> Optional[int]:
        """Returns the index in ``self.update_exam_specs`` of the selected tree row, or None."""
        selection = self.update_exams_tree.selection()
        if not selection:
            return None
        try:
            return int(selection[0])
        except (ValueError, IndexError):
            return None

    def edit_update_exam_label(self) -> None:
        """Edits the label of the selected exam (the name of its '<label>_uso' column)."""
        index = self._selected_update_exam_index()
        if index is None:
            messagebox.showinfo("Información", "Seleccione un examen de la lista para editar su etiqueta.")
            return
        spec = self.update_exam_specs[index]
        new_label = simpledialog.askstring(
            "Editar Etiqueta",
            f"Etiqueta para '{os.path.basename(spec['path'])}'\n"
            f"(se usará como nombre de la columna de uso '<etiqueta>_uso'):",
            initialvalue=spec["label"],
            parent=self.app.root,
        )
        if new_label is None:
            return
        new_label = new_label.strip()
        spec["label"] = new_label or self._default_exam_label(spec["path"])
        self._refresh_update_exams_tree()

    def _on_update_exam_double_click(self, event) -> None:
        """Double-clicking a row in the exams tree edits its label."""
        if self.update_exams_tree.identify_row(event.y):
            self.edit_update_exam_label()

    def remove_update_exam(self) -> None:
        """Removes the selected exam from the list."""
        index = self._selected_update_exam_index()
        if index is None:
            messagebox.showinfo("Información", "Seleccione un examen de la lista para quitarlo.")
            return
        del self.update_exam_specs[index]
        self._refresh_update_exams_tree()

    def clear_update_exams(self) -> None:
        """Empties the list of exams."""
        self.update_exam_specs.clear()
        self._refresh_update_exams_tree()

    def update_bank_with_exams_action(self) -> None:
        """
        Updates the usage statistics of an existing question bank from one or more generated exams.
        Each exam is matched back to the bank by statement and marked as used in its own
        '<label>_uso' column; the aggregated 'Veces usada en examen' column is then recomputed.
        """
        bank_path = self.update_bank_path_var.get()

        if not bank_path:
            messagebox.showerror("Error", "Por favor, seleccione el banco de preguntas a actualizar.")
            return
        if not self.update_exam_specs:
            messagebox.showerror("Error", "Añada al menos un examen para registrar su uso en el banco.")
            return

        exams = [{"path": spec["path"], "label": spec["label"]} for spec in self.update_exam_specs]
        total_matched, df_updated, stats = self.question_bank_manager.update_bank_with_exams(bank_path, exams)

        if total_matched == -1 or df_updated is None:
            messagebox.showerror("Error", "Error al procesar los archivos. Revise la consola para más detalles.")
            return

        # Build a per-exam summary to show the user.
        detail_lines = [
            f"• {os.path.basename(exam['path'])} → '{exam['column']}': {exam['matched']} preguntas"
            for exam in stats.get("exams", [])
        ]
        errors = stats.get("errors", [])
        summary = "\n".join(detail_lines) if detail_lines else "Ningún examen pudo procesarse."
        if errors:
            summary += f"\n\nExámenes omitidos (no se pudieron leer): {len(errors)}"

        if total_matched == 0:
            messagebox.showinfo(
                "Información",
                f"No se emparejó ninguna pregunta de los exámenes con el banco. No se realizaron cambios.\n\n{summary}",
            )
            return

        response = messagebox.askyesnocancel(
            "Guardar Cambios",
            f"Se registraron {total_matched} usos de preguntas en el banco:\n\n{summary}\n\n"
            f"¿Desea guardar los cambios en el banco existente?",
            default='yes',
        )
        if response is True:
            filepath = self.question_bank_manager.save_dataframe_to_excel(df_updated, bank_path, overwrite=True)
            if filepath:
                messagebox.showinfo("Éxito", f"Banco actualizado con {total_matched} usos registrados: {filepath}")
            else:
                messagebox.showerror("Error al guardar", "Error al guardar el banco existente.")
        elif response is False:
            new_filepath = filedialog.asksaveasfilename(
                title="Guardar Banco Actualizado Como...",
                defaultextension=".xlsx",
                initialdir=os.path.dirname(bank_path),
                initialfile=f"{os.path.splitext(os.path.basename(bank_path))[0]}_actualizado.xlsx",
            )
            if new_filepath:
                filepath = self.question_bank_manager.save_dataframe_to_excel(df_updated, new_filepath, overwrite=True)
                if filepath:
                    messagebox.showinfo("Éxito", f"Banco actualizado guardado en: {filepath}")
                else:
                    messagebox.showerror("Error al guardar", "Error al guardar el nuevo archivo.")

    def select_revised_xlsx_output_dir(self) -> None:
        """Opens a dialog to select the output directory for the revised XLSX file."""
        directory = filedialog.askdirectory(title="Seleccionar Directorio de Salida para XLSX Revisado")
        if directory:
            self.revised_xlsx_output_dir_var.set(directory)
