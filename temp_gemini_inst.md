¡Absolutamente! Es una excelente idea para mejorar la usabilidad y permitir al usuario descubrir y seleccionar los modelos más adecuados para su tarea. Reemplazar el `Combobox` estático por una tabla (`ttk.Treeview`) dinámica es una mejora significativa.

Aquí te explico paso a paso cómo modificar tu archivo `main_app.py` para implementar esta funcionalidad.

### Plan de Acción

1.  **Importar `genai`:** Necesitaremos importar la librería de Google en `main_app.py` para poder llamar a `genai.list_models()`.
2.  **Modificar la GUI (`create_question_tab`):**
    *   Eliminaremos el `ttk.Combobox` que muestra los 3 modelos fijos.
    *   Añadiremos un `ttk.Treeview` (el widget de tabla en Tkinter) para mostrar la lista de modelos.
    *   Añadiremos un botón "Cargar Modelos" que, al ser presionado, usará la API key introducida para obtener y mostrar la lista de modelos en la tabla.
3.  **Crear la Lógica de Carga:**
    *   Crearemos una nueva función, por ejemplo `populate_models_table`, que se encargará de:
        *   Configurar `genai` con la API key del usuario.
        *   Llamar a `genai.list_models()`.
        *   Filtrar los modelos para mostrar solo los que son útiles para generar contenido (`'generateContent'`).
        *   Poblar el `Treeview` con los datos de los modelos.
        *   Manejar posibles errores (ej. API key inválida).
4.  **Manejar la Selección:**
    *   Crearemos otra función, `on_model_select`, que se activará cuando el usuario haga clic en una fila de la tabla.
    *   Esta función actualizará la variable `self.selected_model_var` con el nombre técnico del modelo seleccionado, para que el resto de tu aplicación (el `QuestionGenerator`) siga funcionando sin cambios.

---

### Código Modificado: `main_app.py`

A continuación te proporciono el código completo y actualizado de `main_app.py`. He marcado las secciones nuevas o modificadas con comentarios como `### CAMBIO ###` para que puedas ver exactamente qué ha cambiado.

```python
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

### CAMBIO ###
# Importamos la librería de Google para listar los modelos
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
    ... (el resto de la docstring no cambia) ...
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

        ### CAMBIO ###
        # Eliminamos el diccionario estático de modelos.
        # La variable ahora guardará el nombre técnico del modelo seleccionado en la tabla.
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

        self.create_question_tab()
        self.create_manage_bank_tab()
        self.create_exam_tab()

        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Ayuda", menu=help_menu)
        help_menu.add_command(label="Acerca de...", command=self.show_about_dialog)

    # ... (el resto de métodos hasta create_question_tab no cambian) ...
    # load_prompt_types, save_prompt_types, etc. se mantienen igual.

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

        # ... (La sección de Prompts y PDF no cambia) ...
        prompt_type_frame = ttk.LabelFrame(inner_frame_question, text="Seleccionar/Editar Tipo de Prompt")
        prompt_type_frame.pack(padx=10, pady=10, fill='x')
        # ... (código del frame de prompts idéntico) ...
        
        # --- Generation configuration section ---
        config_frame = ttk.LabelFrame(inner_frame_question, text="Configuración de Generación")
        config_frame.pack(padx=10, pady=10, fill='x', expand=True)

        # ... (Las filas 0 a 5 no cambian: num_questions, output_filename, processing_mode, max_attempts, duplicate_filter, prompt_inclusion) ...

        ### CAMBIO ###
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
        
        cols = ('name', 'display_name', 'description')
        self.models_tree = ttk.Treeview(models_table_frame, columns=cols, show='headings', height=5)
        
        # Definir encabezados
        self.models_tree.heading('name', text='Nombre Técnico')
        self.models_tree.heading('display_name', text='Nombre')
        self.models_tree.heading('description', text='Descripción')
        
        # Definir anchos de columna
        self.models_tree.column('name', width=150, stretch=tk.NO)
        self.models_tree.column('display_name', width=150, stretch=tk.NO)
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
        
        model_api_frame.columnconfigure(1, weight=1)
        model_api_frame.rowconfigure(1, weight=1)

        # ... (El resto de filas (7, 8, 9) no cambian: debug_options, output_dir, generate_button) ...
        
        # ... (El resto del método no cambia) ...

    ### CAMBIO ###
    # Nueva función para poblar la tabla de modelos
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

            for model in available_models:
                self.models_tree.insert("", "end", values=(
                    model.name,
                    model.display_name,
                    model.description.replace('\n', ' ') # Evitar saltos de línea en la descripción
                ))
            
            self.update_status(f"Se cargaron {len(available_models)} modelos. Por favor, seleccione uno de la tabla.")

        except Exception as e:
            messagebox.showerror("Error de API", f"No se pudo obtener la lista de modelos. Verifica tu clave API y conexión a internet.\n\nError: {e}")
            self.update_status("Error al cargar modelos.")

    ### CAMBIO ###
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

    # ... (el resto de métodos hasta generate_questions no cambian) ...

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
        
        ### CAMBIO ###
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

        # ... (el resto del método generate_questions no cambia) ...
        # ... (el resto del archivo no cambia) ...
```

### Resumen de los Cambios

1.  **`__init__`**: Se eliminó el diccionario `self.gemini_models` ya que ahora los modelos se obtienen dinámicamente.
2.  **`create_question_tab`**:
    *   Se reemplazó el `ttk.Combobox` por un `ttk.Treeview` con tres columnas: "Nombre Técnico", "Nombre" y "Descripción".
    *   Se añadieron barras de desplazamiento a la tabla.
    *   Se añadió un botón "Cargar Modelos" para iniciar el proceso de obtención de modelos.
    *   Se vinculó el evento de selección de la tabla (`<<TreeviewSelect>>`) a la nueva función `on_model_select`.
3.  **Nueva Función `populate_models_table`**:
    *   Esta función contiene la lógica para usar la API key, llamar a `genai.list_models()`, filtrar los resultados y llenar la tabla. Incluye manejo de errores.
4.  **Nueva Función `on_model_select`**:
    *   Se activa cada vez que el usuario hace clic en una fila.
    *   Extrae el nombre técnico del modelo de la fila seleccionada y lo guarda en `self.selected_model_var`.
5.  **`generate_questions`**:
    *   Ahora, en lugar de buscar en un diccionario, simplemente obtiene el nombre del modelo de `self.selected_model_var.get()`.
    *   Se añadió una comprobación para asegurarse de que el usuario ha seleccionado un modelo antes de generar preguntas.

Con estos cambios, tu aplicación ahora es mucho más flexible y profesional, permitiendo a los usuarios aprovechar cualquier modelo que Google ponga a su disposición sin necesidad de que actualices el código.