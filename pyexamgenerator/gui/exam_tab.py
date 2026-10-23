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

"""The «Generar Exámenes» tab (ARC-1): exams from a question bank (DOCX, XLSX and Moodle XML),
Moodle XML from an existing exam XLSX, and the template of the tab.
"""

import logging
import os
import tkinter as tk
from tkinter import filedialog, ttk
from typing import Any, Dict, List, Optional

import pandas as pd

from pyexamgenerator import gui_logic, schema, user_config
from pyexamgenerator.exam_generator import ExamConfig, ExamGenerator, NoAcceptableQuestionsError
from pyexamgenerator.gui._dialogs import messagebox
from pyexamgenerator.tooltip import ToolTip

logger = logging.getLogger(__name__)


class ExamTab:
    """Widgets, variables and actions of the «Generar Exámenes» tab.

    ``app`` is the :class:`~pyexamgenerator.main_app.ExamApp` that owns the window: the tab uses its
    notebook, status bar, page-scroll helpers and background tasks.
    """

    def __init__(self, app) -> None:
        self.app = app
        self.exam_generator = ExamGenerator()
        # No sample values in the exam data: they ended up in real exams when left unchanged.
        self.excel_filepath = tk.StringVar()
        self.subject = tk.StringVar()
        self.exam_name = tk.StringVar()
        self.course = tk.StringVar()
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
        self.answer_sheet_instructions = tk.StringVar()
        self.penalty = tk.StringVar(value="-25")
        self.xml_cat_additional_text = tk.StringVar()
        self.export_moodle = tk.BooleanVar(value=False)
        self.update_excel = tk.BooleanVar(value=False)
        self.usage_alert_enabled_var = tk.BooleanVar(value=True)
        self.usage_alert_threshold_var = tk.StringVar(value="3")
        self.num_columns_var = tk.StringVar(value="3")
        self.selection_method_var = tk.StringVar(value="diccionario")
        self.total_questions_var = tk.StringVar(value="20")
        self.total_distribution_var = tk.StringVar(value="equitativo")
        self.gen_exams_output_dir_var = tk.StringVar()
        self.gen_session_output_var = tk.StringVar()
        self.existing_exam_xlsx_for_xml_var = tk.StringVar()
        self.existing_exam_xml_output_var = tk.StringVar()
        self.existing_exam_xml_penalty_var = tk.StringVar(value="-25")
        self.existing_exam_xml_cat_text_var = tk.StringVar(value="")
        self.existing_exam_xml_use_answer_text_var = tk.BooleanVar(value=False)
        self.xml_use_answer_text_var = tk.BooleanVar(value=False)
        self.template_docx_path_var = tk.StringVar(value="")

        self.create_exam_tab()

    def create_exam_tab(self):
        """
        Creates the 'Generate Exams' tab with all its widgets.
        """
        canvas_exam, inner_frame_exam = self.app._create_scrollable_tab('Generar Exámenes')

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
        ToolTip(
            exam_names_label,
            text="Opcional: Ingrese nombres específicos para cada examen, separados por coma (ej. Tipo A,Tipo B). Si se deja vacío, se usarán nombres genéricos.",
        )
        exam_names_entry = ttk.Entry(exam_data_frame, width=50, textvariable=self.exam_names)
        exam_names_entry.grid(row=3, column=1, columnspan=2, padx=5, pady=5, sticky='ew')
        ToolTip(exam_names_entry, text="Nombres específicos para los exámenes (opcional).")
        row += 1

        # 3. Question selection by topic (spans the width - managed internally)
        questions_frame = ttk.LabelFrame(inner_frame_exam, text="Selección de Preguntas por Tema")
        questions_frame.grid(row=row, column=0, columnspan=3, padx=10, pady=10, sticky='ew')
        row_interno_questions = 0  # Initialize a row counter for this frame

        select_by_theme_radio = ttk.Radiobutton(
            questions_frame,
            text="Seleccionar cantidad por tema:",
            variable=self.selection_method_var,
            value="por_tema",
            command=self.update_theme_display,
        )
        select_by_theme_radio.grid(row=row_interno_questions, column=0, columnspan=2, sticky='w', pady=5)
        ToolTip(
            select_by_theme_radio,
            text="Permite especificar la cantidad de preguntas a seleccionar para cada tema individualmente.",
        )
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

        same_number_radio = ttk.Radiobutton(
            questions_frame,
            text="Mismo número de preguntas por tema:",
            variable=self.selection_method_var,
            value="mismo_numero",
        )
        same_number_radio.grid(row=row_interno_questions + 1, column=0, sticky='w')
        ToolTip(
            same_number_radio,
            text="Seleccione esta opción para usar la misma cantidad de preguntas para todos los temas.",
        )
        self.num_preguntas_por_tema_entry = ttk.Entry(
            questions_frame, width=5, textvariable=self.num_questions_same_topic
        )
        self.num_preguntas_por_tema_entry.grid(row=row_interno_questions + 1, column=1, padx=5, sticky='ew')
        ToolTip(self.num_preguntas_por_tema_entry, text="Ingrese el número de preguntas a seleccionar de cada tema.")
        row_interno_questions += 2

        dictionary_radio = ttk.Radiobutton(
            questions_frame,
            text="Diccionario de preguntas por tema (Tema01:2,Tema02:3):",
            variable=self.selection_method_var,
            value="diccionario",
        )
        dictionary_radio.grid(row=row_interno_questions + 1, column=0, sticky='w')
        ToolTip(
            dictionary_radio,
            text="Ingrese un diccionario especificando la cantidad de preguntas por tema (ej. TemaA:3,TemaB:2).",
        )
        questions_per_topic_entry = ttk.Entry(questions_frame, textvariable=self.questions_per_topic)
        questions_per_topic_entry.grid(row=row_interno_questions + 1, column=1, padx=5, sticky='ew')
        ToolTip(questions_per_topic_entry, text="Diccionario con el formato Tema:Cantidad.")

        total_radio = ttk.Radiobutton(
            questions_frame, text="Número total de preguntas:", variable=self.selection_method_var, value="total"
        )
        total_radio.grid(row=row_interno_questions + 2, column=0, sticky='w')
        ToolTip(
            total_radio,
            text="Selecciona un número total de preguntas del banco y reparte ese total según el modo elegido.",
        )
        total_questions_entry = ttk.Entry(questions_frame, width=6, textvariable=self.total_questions_var)
        total_questions_entry.grid(row=row_interno_questions + 2, column=1, padx=5, sticky='w')
        ToolTip(total_questions_entry, text="Número total de preguntas que tendrá el examen.")

        total_distribution_label = ttk.Label(questions_frame, text="Reparto del total:")
        total_distribution_label.grid(row=row_interno_questions + 3, column=0, sticky='e', padx=5)
        ToolTip(total_distribution_label, text="Cómo se reparte el número total de preguntas entre los temas.")
        total_distribution_combo = ttk.Combobox(
            questions_frame,
            textvariable=self.total_distribution_var,
            values=["equitativo", "azar"],
            state='readonly',
            width=12,
        )
        total_distribution_combo.grid(row=row_interno_questions + 3, column=1, padx=5, sticky='w')
        ToolTip(
            total_distribution_combo,
            text="equitativo: mismo número de preguntas por tema en la medida de lo posible (los primeros temas reciben una más si el total no es divisible). azar: se eligen del banco completo sin tener en cuenta el tema.",
        )
        row += 1  # Increment the row for the next LabelFrame

        # 4. Selection method (spans 3 columns)
        method_frame = ttk.LabelFrame(inner_frame_exam, text="Método de Selección")
        method_frame.grid(row=row, column=0, columnspan=3, padx=10, pady=10, sticky='ew')
        method_label = ttk.Label(method_frame, text="Método:")
        method_label.grid(row=0, column=0, padx=5, pady=5, sticky='w')
        ToolTip(method_label, text="Seleccione el método para elegir las preguntas dentro de cada tema.")
        method_combo = ttk.Combobox(
            method_frame,
            textvariable=self.selection_method,
            values=["azar", "primeras", "menos usadas"],
            state='readonly',
        )
        method_combo.grid(row=0, column=1, columnspan=2, padx=5, pady=5, sticky='ew')
        ToolTip(
            method_combo,
            text="azar: selecciona preguntas aleatoriamente. primeras: selecciona las primeras preguntas encontradas para el tema. menos usadas: selecciona las preguntas menos usadas.",
        )
        row += 1  # Increment the row for the next LabelFrame

        usage_alert_frame = ttk.LabelFrame(inner_frame_exam, text="Alerta de uso de preguntas")
        usage_alert_frame.grid(row=row, column=0, columnspan=3, padx=10, pady=5, sticky='ew')
        usage_alert_check = ttk.Checkbutton(
            usage_alert_frame,
            text="Avisar si alguna pregunta supera este numero de usos:",
            variable=self.usage_alert_enabled_var,
        )
        usage_alert_check.grid(row=0, column=0, padx=5, pady=5, sticky='w')
        ToolTip(
            usage_alert_check,
            text="Si esta activado, se mostrara una alerta antes de generar cuando alguna pregunta seleccionada tenga mas usos que el umbral indicado.",
        )
        usage_alert_entry = ttk.Entry(usage_alert_frame, width=5, textvariable=self.usage_alert_threshold_var)
        usage_alert_entry.grid(row=0, column=1, padx=5, pady=5, sticky='w')
        ToolTip(
            usage_alert_entry,
            text="Umbral de usos. Por defecto 3; se avisa solo cuando el valor de 'Veces usada en examen' es mayor que este numero.",
        )
        row += 1

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
        ToolTip(
            export_moodle_check,
            text="Marque para generar un archivo XML compatible con la importación de preguntas en Moodle.",
        )

        penalty_label = ttk.Label(moodle_frame, text="Penalización (-%):")
        penalty_label.grid(row=1, column=0, padx=5, pady=5, sticky='w')
        ToolTip(
            penalty_label,
            text="Ingrese el porcentaje de penalización por respuesta incorrecta para la importación en Moodle (ej. -25).",
        )
        penalty_entry = ttk.Entry(moodle_frame, width=5, textvariable=self.penalty)
        penalty_entry.grid(row=1, column=1, padx=5, pady=5, sticky='ew')
        ToolTip(penalty_entry, text="Porcentaje de penalización para Moodle.")
        xml_cat_text_label = ttk.Label(moodle_frame, text="Texto Adicional Moodle XML:")
        xml_cat_text_label.grid(row=2, column=0, columnspan=1, padx=5, pady=5, sticky='w')
        ToolTip(
            xml_cat_text_label,
            text="Opcional: Ingrese texto adicional para la categoría de las preguntas en el archivo XML de Moodle.",
        )
        xml_cat_text_entry = ttk.Entry(moodle_frame, width=50, textvariable=self.xml_cat_additional_text)
        xml_cat_text_entry.grid(row=2, column=1, columnspan=2, padx=5, pady=5, sticky='ew')
        ToolTip(xml_cat_text_entry, text="Texto adicional para la categoría Moodle XML (opcional).")

        xml_non_blank_check = ttk.Checkbutton(
            moodle_frame,
            text="XML no blanco (usar enunciado y respuestas completas)",
            variable=self.xml_use_answer_text_var,
        )
        xml_non_blank_check.grid(row=3, column=0, columnspan=3, padx=5, pady=5, sticky='w')
        ToolTip(
            xml_non_blank_check, text="Si se marca, el XML incluye enunciado y texto de respuestas en lugar de a/b/c/d."
        )

        suggest_moodle_button = ttk.Button(
            moodle_frame, text="Sugerir nombres Moodle", command=self.show_moodle_suggestions
        )
        suggest_moodle_button.grid(row=4, column=0, columnspan=3, padx=5, pady=5, sticky='w')
        ToolTip(
            suggest_moodle_button,
            text="Muestra nombres de cuestionario y columnas recomendados para que el xlsx exportado de Moodle sea identificable por el corrector.",
        )
        row += 1

        # 7. Generate Moodle XML from an existing generated exam XLSX (spans 3 columns)
        existing_xlsx_xml_frame = ttk.LabelFrame(inner_frame_exam, text="Generar Moodle XML desde XLSX de Examen")
        existing_xlsx_xml_frame.grid(row=row, column=0, columnspan=3, padx=10, pady=10, sticky='ew')
        ToolTip(
            existing_xlsx_xml_frame,
            text="Convierte un archivo de examen ya generado (normalmente '*_completo.xlsx') en un XML de Moodle sin volver a generar el examen.",
        )

        xml_source_label = ttk.Label(existing_xlsx_xml_frame, text="XLSX del Examen:")
        xml_source_label.grid(row=0, column=0, padx=5, pady=5, sticky='w')
        ToolTip(
            xml_source_label,
            text="Seleccione el archivo XLSX del examen (preferiblemente el que termina en '_completo.xlsx').",
        )

        xml_source_entry = ttk.Entry(
            existing_xlsx_xml_frame, width=50, textvariable=self.existing_exam_xlsx_for_xml_var
        )
        xml_source_entry.grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        ToolTip(xml_source_entry, text="Ruta del XLSX de examen desde el que se generará el XML.")

        xml_source_button = ttk.Button(
            existing_xlsx_xml_frame, text="Seleccionar XLSX", command=self.select_existing_exam_xlsx_for_xml
        )
        xml_source_button.grid(row=0, column=2, padx=5, pady=5)
        ToolTip(xml_source_button, text="Abre un diálogo para seleccionar el XLSX del examen.")

        xml_output_label = ttk.Label(existing_xlsx_xml_frame, text="XML de Salida (opcional):")
        xml_output_label.grid(row=1, column=0, padx=5, pady=5, sticky='w')
        ToolTip(
            xml_output_label, text="Ruta del XML de salida. Si se deja vacía, se usará el mismo nombre base del XLSX."
        )

        xml_output_entry = ttk.Entry(existing_xlsx_xml_frame, width=50, textvariable=self.existing_exam_xml_output_var)
        xml_output_entry.grid(row=1, column=1, padx=5, pady=5, sticky='ew')
        ToolTip(xml_output_entry, text="Ruta de salida para el XML de Moodle.")

        xml_output_button = ttk.Button(
            existing_xlsx_xml_frame, text="Seleccionar XML", command=self.select_existing_exam_xml_output
        )
        xml_output_button.grid(row=1, column=2, padx=5, pady=5)
        ToolTip(xml_output_button, text="Elegir dónde guardar el XML generado.")

        xml_penalty_label = ttk.Label(existing_xlsx_xml_frame, text="Penalización (-%):")
        xml_penalty_label.grid(row=2, column=0, padx=5, pady=5, sticky='w')
        ToolTip(
            xml_penalty_label,
            text="Penalización por respuesta incorrecta. Admite decimales (ej. -33.333333 para 4 opciones).",
        )

        xml_penalty_entry = ttk.Entry(
            existing_xlsx_xml_frame, width=10, textvariable=self.existing_exam_xml_penalty_var
        )
        xml_penalty_entry.grid(row=2, column=1, padx=5, pady=5, sticky='w')
        ToolTip(xml_penalty_entry, text="Porcentaje de penalización para respuestas incorrectas en Moodle.")

        xml_cat_extra_label = ttk.Label(existing_xlsx_xml_frame, text="Texto adicional categoría XML:")
        xml_cat_extra_label.grid(row=3, column=0, padx=5, pady=5, sticky='w')
        ToolTip(xml_cat_extra_label, text="Texto opcional que se añadirá al nombre de categoría en Moodle.")

        xml_cat_extra_entry = ttk.Entry(
            existing_xlsx_xml_frame, width=50, textvariable=self.existing_exam_xml_cat_text_var
        )
        xml_cat_extra_entry.grid(row=3, column=1, padx=5, pady=5, sticky='ew')
        ToolTip(xml_cat_extra_entry, text="Texto adicional para la categoría Moodle (opcional).")

        xml_full_text_check = ttk.Checkbutton(
            existing_xlsx_xml_frame,
            text="XML no blanco (usar enunciado y respuestas completas)",
            variable=self.existing_exam_xml_use_answer_text_var,
        )
        xml_full_text_check.grid(row=4, column=0, columnspan=3, padx=5, pady=5, sticky='w')
        ToolTip(
            xml_full_text_check,
            text="Si se marca, el XML incluirá enunciados y respuestas completas en lugar de a/b/c/d.",
        )

        generate_xml_button = ttk.Button(
            existing_xlsx_xml_frame,
            text="Generar XML Moodle desde XLSX",
            command=self.generate_moodle_xml_from_existing_xlsx_action,
        )
        generate_xml_button.grid(row=5, column=0, columnspan=3, pady=10)
        ToolTip(generate_xml_button, text="Genera el XML de Moodle a partir del XLSX seleccionado.")

        existing_xlsx_xml_frame.columnconfigure(1, weight=1)
        row += 1

        # 8. Update excel file with usage (spans 3 columns)
        update_excel_frame = ttk.Frame(inner_frame_exam)
        update_excel_frame.grid(row=row, column=0, columnspan=3, padx=10, pady=10, sticky='ew')
        update_excel_check = ttk.Checkbutton(
            update_excel_frame, text="Actualizar Archivo Excel con Uso", variable=self.update_excel
        )
        update_excel_check.pack(side='left', padx=5)
        ToolTip(
            update_excel_check,
            text="Marque para actualizar el archivo Excel indicando qué preguntas se han utilizado en el examen.",
        )

        exam_template_buttons = ttk.Frame(update_excel_frame)
        exam_template_buttons.pack(side='right', padx=5)
        ttk.Button(exam_template_buttons, text="Guardar Plantilla", command=self.save_exam_tab_template).pack(
            side='left', padx=2
        )
        ttk.Button(exam_template_buttons, text="Cargar Plantilla", command=self.load_exam_tab_template).pack(
            side='left', padx=2
        )
        ToolTip(exam_template_buttons, text="Guardar o cargar la configuración de la pestaña Generar Exámenes.")
        row += 1

        template_docx_frame = ttk.LabelFrame(inner_frame_exam, text="Plantilla DOCX (opcional)")
        template_docx_frame.grid(row=row, column=0, columnspan=3, padx=10, pady=5, sticky='ew')
        template_docx_entry = ttk.Entry(template_docx_frame, textvariable=self.template_docx_path_var)
        template_docx_entry.pack(side='left', fill='x', expand=True, padx=5, pady=5)
        ToolTip(
            template_docx_entry,
            "Ruta del archivo DOCX de plantilla. Placeholders soportados: {{subject}}, {{exam}}, {{course}}, {{exam_type}}",
        )
        template_docx_button = ttk.Button(
            template_docx_frame, text="Seleccionar Plantilla", command=self.select_template_docx_file
        )
        template_docx_button.pack(side='left', padx=5, pady=5)
        ToolTip(template_docx_button, "Seleccionar una plantilla DOCX base para el examen.")
        row += 1

        # Output path
        exam_output_dir_frame = ttk.LabelFrame(inner_frame_exam, text="Directorio de Salida para Exámenes")
        exam_output_dir_frame.grid(row=row, column=0, columnspan=3, padx=10, pady=10, sticky='ew')
        ToolTip(
            exam_output_dir_frame,
            "Carpeta donde se guardarán los exámenes generados. Si se deja en blanco, se usará la misma carpeta que el banco de preguntas.",
        )

        exam_output_dir_entry = ttk.Entry(exam_output_dir_frame, textvariable=self.gen_exams_output_dir_var)
        exam_output_dir_entry.pack(side='left', fill='x', expand=True, padx=5, pady=5)
        ToolTip(exam_output_dir_entry, "Ruta al directorio de salida para los exámenes.")

        exam_output_dir_button = ttk.Button(
            exam_output_dir_frame, text="Seleccionar...", command=self.select_gen_exams_output_dir
        )
        exam_output_dir_button.pack(side='left', padx=5, pady=5)
        ToolTip(exam_output_dir_button, "Abrir diálogo para seleccionar el directorio de salida.")
        row += 1

        # Resumable grading session (optional)
        session_frame = ttk.LabelFrame(inner_frame_exam, text="Sesión de corrección (opcional)")
        session_frame.grid(row=row, column=0, columnspan=3, padx=10, pady=5, sticky='ew')
        ToolTip(
            session_frame,
            "Si indicas una ruta, se guardará una sesión (.pkl + .json) con las rutas de los exámenes generados para retomar la corrección sin volver a indicarlas.",
        )
        session_entry = ttk.Entry(session_frame, textvariable=self.gen_session_output_var)
        session_entry.pack(side='left', fill='x', expand=True, padx=5, pady=5)
        ToolTip(session_entry, "Ruta base de la sesión (sin extensión, o con .json/.pkl).")
        session_button = ttk.Button(session_frame, text="Seleccionar...", command=self.select_gen_session_output)
        session_button.pack(side='left', padx=5, pady=5)
        ToolTip(session_button, "Elegir dónde guardar la sesión de corrección.")
        row += 1

        # Generate Exams Button (spans the width)
        self.generate_exams_button = ttk.Button(inner_frame_exam, text="Generar Exámenes", command=self.generate_exams)
        self.generate_exams_button.grid(row=row, column=0, columnspan=3, pady=20)
        ToolTip(
            self.generate_exams_button,
            "Genera los archivos de examen (docx y opcionalmente xml) con la configuración actual.",
        )

        inner_frame_exam.columnconfigure(0, weight=1)
        inner_frame_exam.columnconfigure(1, weight=1)
        inner_frame_exam.columnconfigure(2, weight=1)

        self.app._bind_page_scroll(canvas_exam, canvas_exam)

    def select_existing_exam_xlsx_for_xml(self) -> None:
        """Opens a dialog to select an already generated exam XLSX file for XML export."""
        filepath = filedialog.askopenfilename(
            title="Seleccionar Examen XLSX", filetypes=[("Archivos Excel", "*.xlsx;*.xls")]
        )
        if filepath:
            self.existing_exam_xlsx_for_xml_var.set(filepath)
            if not self.existing_exam_xml_output_var.get().strip():
                xml_base = os.path.splitext(filepath)[0]
                if xml_base.lower().endswith("_completo"):
                    xml_base = xml_base[: -len("_completo")]
                self.existing_exam_xml_output_var.set(f"{xml_base}.xml")

    def select_existing_exam_xml_output(self) -> None:
        """Opens a dialog to choose the output path of the generated Moodle XML."""
        source_xlsx = self.existing_exam_xlsx_for_xml_var.get().strip()
        initial_dir = os.path.dirname(source_xlsx) if source_xlsx else os.getcwd()
        initial_file = "examen.xml"
        if source_xlsx:
            xml_base = os.path.splitext(os.path.basename(source_xlsx))[0]
            if xml_base.lower().endswith("_completo"):
                xml_base = xml_base[: -len("_completo")]
            initial_file = f"{xml_base}.xml"

        filepath = filedialog.asksaveasfilename(
            title="Guardar Moodle XML como...",
            defaultextension=".xml",
            initialdir=initial_dir,
            initialfile=initial_file,
            filetypes=[("Archivos XML", "*.xml")],
        )
        if filepath:
            self.existing_exam_xml_output_var.set(filepath)

    def generate_moodle_xml_from_existing_xlsx_action(self) -> None:
        """Generates Moodle XML from a selected existing exam XLSX file."""
        exam_xlsx_path = self.existing_exam_xlsx_for_xml_var.get().strip()
        xml_output_path = self.existing_exam_xml_output_var.get().strip() or None
        xml_cat_additional_text = self.existing_exam_xml_cat_text_var.get().strip() or None
        xml_use_answer_text = self.existing_exam_xml_use_answer_text_var.get()

        if not exam_xlsx_path:
            messagebox.showerror("Error", "Por favor, seleccione un archivo XLSX de examen.")
            return
        if not os.path.exists(exam_xlsx_path):
            messagebox.showerror("Error", f"El archivo XLSX '{exam_xlsx_path}' no se encuentra.")
            return

        try:
            penalty = gui_logic.parse_penalty(self.existing_exam_xml_penalty_var.get(), default=-25.0)
        except ValueError:
            messagebox.showerror("Error", "La penalización debe ser numérica (puede usar coma o punto decimal).")
            return

        self.app.update_status("Generando XML Moodle desde XLSX existente...")
        try:
            generated_xml_path = self.exam_generator.generate_moodle_xml_from_existing_exam_xlsx(
                exam_xlsx_path=exam_xlsx_path,
                xml_output_path=xml_output_path,
                xml_cat_additional_text=xml_cat_additional_text,
                penalty=penalty,
                xml_use_answer_text=xml_use_answer_text,
            )
            self.existing_exam_xml_output_var.set(generated_xml_path)
            self.app.update_status("XML Moodle generado.")
            messagebox.showinfo("Éxito", f"Archivo XML generado correctamente en:\n{generated_xml_path}")
        except Exception as e:
            self.app.update_status(f"Error al generar XML Moodle: {e}")
            messagebox.showerror("Error", f"No se pudo generar el XML de Moodle:\n{e}")

    def load_themes_for_selection(self) -> None:
        """
        Loads themes from an Excel file for the 'questions per theme' selection UI.
        It reads the 'Tema' column and dynamically creates Spinbox widgets for each unique theme.
        If the bank cannot be used, the reason is shown in place of the themes and in the status
        bar (it used to reach only the console).
        """
        # Clear existing widgets
        for widget in self.by_theme_frame.winfo_children():
            widget.destroy()
        self.theme_quantity_widgets = {}  # Reset the widget dictionary.

        excel_path = self.excel_filepath.get().strip()
        if not excel_path:
            return
        problem = None
        unique_themes: List[Any] = []
        if not os.path.exists(excel_path):
            problem = f"No se encuentra el banco de preguntas: {excel_path}"
        else:
            try:
                df = pd.read_excel(excel_path)
            except Exception as exc:  # noqa: BLE001 - shown to the user
                problem = f"No se pudo leer el banco de preguntas ({exc})."
            else:
                if schema.TOPIC not in df.columns:
                    problem = "El banco de preguntas no tiene la columna 'Tema'."
                else:
                    # An empty cell is not a topic, and sorting as text tolerates mixed types
                    # (sorting NaN with text failed and left the list empty).
                    topics = [t for t in df[schema.TOPIC].dropna().unique() if str(t).strip()]
                    unique_themes = sorted(topics, key=str)
        if problem:
            ttk.Label(self.by_theme_frame, text=problem, wraplength=500).grid(
                row=0, column=0, padx=5, pady=2, sticky='w'
            )
            self.app.update_status(problem)
            return

        try:
            num_cols = int(self.num_columns_var.get())
            if num_cols < 1:
                num_cols = 1  # Ensure at least 1 column.
        except ValueError:
            num_cols = 3  # Default value if not a valid number.

        row = 0
        col = 0

        for theme in unique_themes:
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
            filetypes=(("Archivos Excel", "*.xlsx *.xls"), ("Todos los archivos", "*.*")),
        )
        if filepath:
            self.excel_filepath.set(filepath)
            # Load themes after selecting a file.
            self.load_themes_for_selection()

    def _read_bank_with_topics(self, excel_path: str) -> Optional[pd.DataFrame]:
        """Reads the bank to list its topics; shows the problem and returns None if it cannot.

        Before, a missing or locked file (open in Excel) raised an error that only reached the
        console, or was reported as an invalid number.
        """
        try:
            df = pd.read_excel(excel_path)
        except Exception as exc:  # noqa: BLE001 - shown to the user
            messagebox.showerror("Error", f"No se pudo leer el banco de preguntas:\n{excel_path}\n\n{exc}")
            return None
        if schema.TOPIC not in df.columns:
            messagebox.showerror("Error", "La columna 'Tema' no se encontró en el archivo Excel.")
            return None
        return df

    def generate_exams(self) -> None:
        """
        Gathers all parameters from the 'Generate Exams' tab and triggers the exam generation process.
        It validates user input, constructs the `questions_per_topic` dictionary, and calls the
        `generate_exam_from_excel` method from the backend `pyexamgenerator` class.
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
        xml_use_answer_text = self.xml_use_answer_text_var.get()
        template_docx_path = self.template_docx_path_var.get().strip() or None
        usage_alert_enabled = self.usage_alert_enabled_var.get()
        usage_alert_threshold_str = self.usage_alert_threshold_var.get().strip()

        if not excel_path.strip():
            messagebox.showerror("Error", "Selecciona el archivo Excel del banco de preguntas.")
            return
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
            penalty = gui_logic.parse_penalty(penalty_str, default=-25.0)
            usage_alert_threshold = int(usage_alert_threshold_str) if usage_alert_threshold_str else 3
            if usage_alert_threshold < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror(
                "Error",
                "Por favor, introduce valores numericos validos para los margenes, tamano de fuente, numero de examenes, penalizacion (admite decimales) y umbral de alerta.",
            )
            return

        exam_name_list = gui_logic.parse_exam_names(exam_names_str)

        questions_per_topic = {}
        total_questions = None
        total_distribution = self.total_distribution_var.get()

        if selection_method_var == "total":
            total_questions_str = self.total_questions_var.get().strip()
            try:
                total_questions = int(total_questions_str)
            except ValueError:
                messagebox.showerror(
                    "Error", "Por favor, introduce un número entero válido para el 'Número total de preguntas'."
                )
                return
            if total_questions <= 0:
                messagebox.showerror("Error", "El 'Número total de preguntas' debe ser mayor que 0.")
                return
        elif selection_method_var == "diccionario":
            try:
                questions_per_topic = gui_logic.parse_questions_per_topic(self.questions_per_topic.get())
            except ValueError:
                messagebox.showerror(
                    "Error",
                    "Formato incorrecto para 'Diccionario de preguntas por tema'. Debe ser 'Tema 01:2, Tema 02:3', etc.",
                )
                return
        elif selection_method_var == "mismo_numero":
            num_preguntas_str = self.num_preguntas_por_tema_entry.get()
            if num_preguntas_str:
                try:
                    num_preguntas = int(num_preguntas_str)
                except ValueError:
                    messagebox.showerror(
                        "Error",
                        "Por favor, introduce un número entero válido para 'Mismo número de preguntas por tema'.",
                    )
                    return
                df_temp = self._read_bank_with_topics(excel_path)
                if df_temp is None:
                    return
                for theme in df_temp[schema.TOPIC].unique():
                    questions_per_topic[theme] = num_preguntas
            else:
                messagebox.showinfo("Información", "Por favor, introduce el número de preguntas por tema.")
                return
        elif selection_method_var == "por_tema":
            df_temp = self._read_bank_with_topics(excel_path)
            if df_temp is None:
                return
            if schema.TOPIC in df_temp.columns:
                unique_themes = df_temp[schema.TOPIC].unique()
                for theme in unique_themes:
                    if theme in self.theme_quantity_widgets:
                        quantity_str = self.theme_quantity_widgets[theme].get()
                        try:
                            quantity = int(quantity_str)
                            if quantity > 0:  # Only include themes with quantity greater than 0.
                                questions_per_topic[theme] = quantity
                        except ValueError:
                            messagebox.showerror(
                                "Error",
                                f"Por favor, introduce un número entero válido para la cantidad de preguntas del tema '{theme}'.",
                            )
                            return
            else:
                messagebox.showerror("Error", "La columna 'Tema' no se encontró en el archivo Excel.")
                return

        output_dir_value = self.gen_exams_output_dir_var.get() or None
        session_output_path = self.gen_session_output_var.get().strip() or None
        # A generator per run: the instance keeps state while it works and the shared one may be in
        # use by «Generar XML desde XLSX existente» while this run goes on in another thread.
        generator = ExamGenerator()

        def confirm_usage_warning(_warning_df: pd.DataFrame, _threshold: int, message: str) -> bool:
            # Called from the worker thread: the dialog is shown in the main thread.
            return self.app._call_in_main_thread(
                lambda: messagebox.askyesno(
                    "Alerta de uso de preguntas", f"{message}\n\nDeseas continuar con la generacion?"
                )
            )

        config = ExamConfig(
            output_dir=output_dir_value,
            exam_names=exam_name_list,
            questions_per_topic=questions_per_topic,
            selection_method=selection_method,
            total_questions=total_questions,
            total_distribution=total_distribution,
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
            xml_use_answer_text=xml_use_answer_text,
            update_excel=update_excel,
            answer_sheet_instructions=answer_sheet_instructions,
            template_docx_path=template_docx_path,
            session_output_path=session_output_path,
            usage_warning_enabled=usage_alert_enabled,
            usage_warning_threshold=usage_alert_threshold,
            usage_warning_callback=confirm_usage_warning if usage_alert_enabled else None,
        )

        def work():
            generator.generate_exam_from_excel(excel_path, config)
            return bool(getattr(generator, "generation_cancelled", False)), getattr(
                generator, "bank_update_error", None
            )

        def on_success(outcome):
            cancelled, bank_update_error = outcome
            if cancelled:
                self.app.update_status("Generacion de examenes cancelada.")
                messagebox.showinfo("Cancelado", "Generacion de examenes cancelada por la alerta de uso de preguntas.")
                return
            self.app.update_status("Exámenes generados.")
            if bank_update_error:
                # The exams exist, but the bank does not record their use (e.g. it was open in Excel).
                messagebox.showwarning(
                    "Banco sin actualizar",
                    "Los exámenes se han generado, pero no se pudo registrar su uso en el banco de preguntas:\n"
                    f"{bank_update_error}\n\n"
                    "Cierra el banco si está abierto en Excel y registra el uso con «Actualizar Banco con "
                    "Exámenes» (pestaña «Gestionar Banco de Preguntas»).",
                )
                return
            messagebox.showinfo("Éxito", "Exámenes generados correctamente.")

        def on_error(e):
            if isinstance(e, (NoAcceptableQuestionsError, ValueError)):
                # Capturamos nuestro error personalizado y el ValueError del bucle
                error_message = (
                    "No se pudo generar el examen. Revisa el estado de las preguntas en tu banco.\n\n"
                    "Es posible que no haya preguntas 'Aceptables' o que estés solicitando más preguntas "
                    "de las disponibles para un tema."
                )
                detailed_error = f"Detalle del error: {e}"

                self.app.update_status("Error: No se encontraron preguntas aceptables o suficientes.")
                messagebox.showerror("Error en el Banco de Preguntas", f"{error_message}\n\n{detailed_error}")
                logger.error(f"ERROR: {error_message}\n{detailed_error}")
            else:
                # Mantenemos un bloque genérico para cualquier otro error inesperado
                self.app.update_status(f"Error al generar exámenes: {e}")
                messagebox.showerror("Error", f"Ocurrió un error inesperado al generar los exámenes: {e}")

        self.app._run_in_background(
            "Generando exámenes...", work, on_success, on_error, widgets=[self.generate_exams_button]
        )

    def show_moodle_suggestions(self) -> None:
        """Shows recommended Moodle quiz names / columns so the exported xlsx is identifiable."""
        exam = self.exam_name.get().strip() or "Examen"
        exam_types = gui_logic.parse_exam_names(self.exam_names.get()) or ["1A"]

        lines = [
            "Usa estos nombres al crear los cuestionarios en Moodle para que las columnas del",
            "xlsx exportado sean reconocibles por el corrector (formato de tipo recomendado: 1A, 1B…).",
            "",
        ]
        for exam_type in exam_types:
            suggestion = ExamGenerator.suggest_moodle_config(exam=exam, exam_type=exam_type)
            lines.append(f"Tipo «{exam_type}»:")
            lines.append(f"   Nombre del cuestionario: {suggestion.get('exam_quiz_name', '')}")
            lines.append(f"   Columna esperada en el xlsx: {suggestion.get('exam_grade_column', '')}")
            lines.append("")

        category = ExamGenerator.suggest_moodle_config(exam=exam, exam_type=exam_types[0]).get("category_name", "")
        lines.append(f"Categoría Moodle sugerida: {category}")

        messagebox.showinfo("Sugerencias de nombres Moodle", "\n".join(lines))

    def select_gen_exams_output_dir(self) -> None:
        """Opens a dialog to select the output directory for generated exams."""
        directory = filedialog.askdirectory(title="Seleccionar Directorio de Salida para Exámenes")
        if directory:
            self.gen_exams_output_dir_var.set(directory)

    def select_gen_session_output(self) -> None:
        """Opens a dialog to choose where to save the resumable grading session."""
        filepath = filedialog.asksaveasfilename(
            title="Guardar sesión de corrección",
            defaultextension=".json",
            initialfile="sesion_correccion.json",
            filetypes=[("Sesión", "*.json *.pkl")],
        )
        if filepath:
            self.gen_session_output_var.set(filepath)

    def select_template_docx_file(self) -> None:
        """Opens a dialog to select a DOCX template for exam generation."""
        filepath = filedialog.askopenfilename(
            title="Seleccionar Plantilla DOCX", filetypes=[("Archivos Word", "*.docx")]
        )
        if filepath:
            self.template_docx_path_var.set(filepath)

    def _exam_template_fields(self) -> Dict[str, tk.Variable]:
        """Fields of the exam tab saved in the exam template, by their key in the JSON file."""
        return {
            "subject": self.subject,
            "exam_name": self.exam_name,
            "course": self.course,
            "num_exams": self.num_exams,
            "exam_names": self.exam_names,
            "questions_per_topic": self.questions_per_topic,
            "num_questions_same_topic": self.num_questions_same_topic,
            "selection_method": self.selection_method,
            "selection_method_var": self.selection_method_var,
            "total_questions": self.total_questions_var,
            "total_distribution": self.total_distribution_var,
            "top_margin": self.top_margin,
            "bottom_margin": self.bottom_margin,
            "left_margin": self.left_margin,
            "right_margin": self.right_margin,
            "font_size": self.font_size,
            "answer_sheet_instructions": self.answer_sheet_instructions,
            "penalty": self.penalty,
            "xml_cat_additional_text": self.xml_cat_additional_text,
            "export_moodle": self.export_moodle,
            "update_excel": self.update_excel,
            "usage_alert_enabled": self.usage_alert_enabled_var,
            "usage_alert_threshold": self.usage_alert_threshold_var,
            "xml_use_answer_text": self.xml_use_answer_text_var,
            "template_docx_path": self.template_docx_path_var,
        }

    def save_exam_tab_template(self) -> None:
        """Saves the current exam-tab values to the template in the user's configuration folder."""
        template_data = {key: var.get() for key, var in self._exam_template_fields().items()}
        try:
            saved_path = user_config.write_json(user_config.EXAM_TEMPLATE_FILE, template_data)
        except OSError as exc:
            messagebox.showerror("Error", f"No se pudo guardar la plantilla de exámenes:\n{exc}")
            return
        messagebox.showinfo("Plantilla", f"Plantilla guardada en:\n{saved_path}")

    def load_exam_tab_template(self) -> None:
        """Loads the exam-tab values from the template in the user's configuration folder."""
        loaded_path = user_config.config_path(user_config.EXAM_TEMPLATE_FILE)
        try:
            config = user_config.read_json(user_config.EXAM_TEMPLATE_FILE)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Error", f"No se pudo leer la plantilla de exámenes:\n{loaded_path}\n\n{exc}")
            return
        if not config:
            messagebox.showwarning("Plantilla", "Todavía no has guardado ninguna plantilla de exámenes.")
            return

        for key, var in self._exam_template_fields().items():
            if key in config:
                var.set(config[key])

        self.app.update_status(f"Plantilla cargada desde: {loaded_path}")
