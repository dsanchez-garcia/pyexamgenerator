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

"""
Assistant window to generate questions WITHOUT an API key.

The user copies each prompt into a web chat (Google AI Studio, ChatGPT or Claude),
attaches the indicated file when needed, pastes the answer back and saves the questions
in the same review files produced by the API workflow.
"""

import json
import os
import subprocess
import sys
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import Callable, Dict, Optional

import pandas as pd

from pyexamgenerator.ai_providers import PROVIDERS, resolve_provider
from pyexamgenerator.question_generator import QuestionGenerator
from pyexamgenerator.question_parsing import QUESTIONS_JSON_SCHEMA, parse_questions_response
from pyexamgenerator.tooltip import ToolTip

_COMMON_TIP = (
    "Inicia una conversación nueva para cada prompt. Pide como mucho 10-15 preguntas por mensaje para evitar "
    "respuestas cortadas; si se corta, usa 'Copiar petición de continuación' y pega la nueva respuesta debajo "
    "de la anterior (se aprovechan todas las preguntas completas). Copia la respuesta con el botón de copiar "
    "del bloque de código o del mensaje."
)

_TARGET_TIPS = {
    "gemini": (
        "Google AI Studio: gratuito con límites diarios. En 'Run settings' puedes activar 'Structured output' "
        "y pegar el esquema ('Copiar esquema JSON') para recibir JSON limpio; revisa también 'Output length' "
        "si la respuesta se corta. Adjunta el PDF o la imagen con el botón '+' cuando la columna 'Adjuntar' lo indique."
    ),
    "openai": (
        "ChatGPT: si pegas un prompt muy largo, ChatGPT puede convertirlo en un archivo adjunto (es normal). "
        "En el plan gratuito el número de archivos por día y las páginas que se leen de cada documento son "
        "limitados: usa fragmentos pequeños o el modo 'text'."
    ),
    "anthropic": (
        "Claude: los textos muy largos se pegan como adjunto ('Pasted'); si llegase vacío, guarda el prompt en un "
        ".txt y súbelo. Si Claude muestra la respuesta como artefacto, cópiala con su botón. Los PDFs de hasta "
        "100 páginas se analizan con texto e imágenes. El plan gratuito tiene un límite de uso por sesión."
    ),
}


def _open_path(path: str) -> None:
    """Opens a file or folder with the default application of the system."""
    if sys.platform.startswith("win"):
        os.startfile(path)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


class WebChatAssistant(tk.Toplevel):
    """
    Toplevel window of the manual (no API) workflow.

    Args:
        master: Parent window.
        generator (~pyexamgenerator.question_generator.QuestionGenerator): Generator used to build the
            prompts (no API key needed).
        prompts_df (pd.DataFrame): Result of :meth:`QuestionGenerator.build_generation_prompts`.
        output_dir (str): Folder where the review files are written.
        output_filename (str): Base name of the output files.
        existing_bank_path (Optional[str]): Bank for the similarity filter.
        similarity_threshold (Optional[float]): Similarity threshold (None disables the filter).
        questions_per_prompt (int): Questions requested per prompt (for the continuation message).
        default_target (str): Provider whose web chat is preselected.
        status_callback (Optional[Callable[[str], None]]): Receives status messages for the main window.
    """

    def __init__(
            self,
            master,
            generator: QuestionGenerator,
            prompts_df: pd.DataFrame,
            output_dir: str,
            output_filename: str,
            existing_bank_path: Optional[str] = None,
            similarity_threshold: Optional[float] = None,
            questions_per_prompt: int = 5,
            default_target: str = "gemini",
            status_callback: Optional[Callable[[str], None]] = None,
    ):
        super().__init__(master)
        self.title("Generar preguntas sin API (copiar y pegar en el chat)")
        self.geometry("1100x780")
        self.generator = generator
        self.prompts_df = prompts_df.reset_index(drop=True)
        self.output_dir = output_dir
        self.output_filename = output_filename
        self.existing_bank_path = existing_bank_path
        self.similarity_threshold = similarity_threshold
        self.questions_per_prompt = questions_per_prompt
        self.status_callback = status_callback
        self.responses: Dict[int, str] = {}
        self.saved = True
        self.current_index: Optional[int] = None

        try:
            target_key = resolve_provider(default_target)
        except ValueError:
            target_key = "gemini"
        self.target_var = tk.StringVar(value=PROVIDERS[target_key].chat_name)
        self.tip_var = tk.StringVar()
        self.info_var = tk.StringVar()

        self._build_widgets()
        self._on_target_change()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        if len(self.prompts_df):
            first = self.tree.get_children()[0]
            self.tree.selection_set(first)
            self.tree.focus(first)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _build_widgets(self) -> None:
        target_frame = ttk.LabelFrame(self, text="Chat de destino")
        target_frame.pack(fill='x', padx=10, pady=(10, 5))
        ttk.Label(target_frame, text="Chat:").grid(row=0, column=0, padx=5, pady=5, sticky='w')
        target_combo = ttk.Combobox(target_frame, textvariable=self.target_var, state='readonly', width=22,
                                    values=[spec.chat_name for spec in PROVIDERS.values()])
        target_combo.grid(row=0, column=1, padx=5, pady=5, sticky='w')
        target_combo.bind("<<ComboboxSelected>>", self._on_target_change)
        ToolTip(target_combo, "Web de chat donde vas a pegar los prompts. No se necesita clave API.")
        open_chat_button = ttk.Button(target_frame, text="Abrir chat en el navegador", command=self._open_chat)
        open_chat_button.grid(row=0, column=2, padx=5, pady=5)
        ToolTip(open_chat_button, "Abre la web del chat seleccionado en una pestaña nueva.")
        schema_button = ttk.Button(target_frame, text="Copiar esquema JSON", command=self._copy_schema)
        schema_button.grid(row=0, column=3, padx=5, pady=5)
        ToolTip(schema_button, "Copia el esquema JSON de la respuesta. En Google AI Studio puedes pegarlo en "
                               "'Run settings' > 'Structured output' para obtener JSON limpio.")
        ttk.Label(target_frame, textvariable=self.tip_var, wraplength=1040, justify='left',
                  foreground="#444444").grid(row=1, column=0, columnspan=4, padx=5, pady=(0, 5), sticky='w')

        table_frame = ttk.LabelFrame(self, text="Prompts (uno por PDF/fragmento)")
        table_frame.pack(fill='x', padx=10, pady=5)
        columns = ("n", "tema", "fragmento", "paginas", "adjuntar", "caracteres", "estado")
        self.tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=7, selectmode='browse')
        for column, heading, width in (
                ("n", "Nº", 40), ("tema", "Tema", 220), ("fragmento", "Fragmento", 80), ("paginas", "Páginas", 110),
                ("adjuntar", "Adjuntar", 260), ("caracteres", "Caracteres", 80), ("estado", "Estado", 220)):
            self.tree.heading(column, text=heading)
            self.tree.column(column, width=width, stretch=column in ("tema", "adjuntar", "estado"))
        tree_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.pack(side='left', fill='x', expand=True, padx=(5, 0), pady=5)
        tree_scroll.pack(side='left', fill='y', pady=5)
        for index, row in self.prompts_df.iterrows():
            attachments = "; ".join(os.path.basename(path) for path in str(row.get("Adjuntar", "") or "").split("; ") if path)
            self.tree.insert("", "end", iid=str(index), values=(
                index + 1, row.get("Tema", ""), f"{row.get('Fragmento', 1)}/{row.get('Total fragmentos', 1)}",
                row.get("Páginas", ""), attachments or "-", row.get("Caracteres", ""), "Pendiente",
            ))
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        panes = ttk.PanedWindow(self, orient='horizontal')
        panes.pack(fill='both', expand=True, padx=10, pady=5)

        prompt_frame = ttk.LabelFrame(panes, text="1. Prompt: cópialo y pégalo en el chat")
        self.prompt_text = scrolledtext.ScrolledText(prompt_frame, wrap=tk.WORD, height=18)
        self.prompt_text.pack(fill='both', expand=True, padx=5, pady=5)
        self.prompt_text.config(state='disabled')
        prompt_buttons = ttk.Frame(prompt_frame)
        prompt_buttons.pack(fill='x', padx=5, pady=(0, 5))
        copy_prompt_button = ttk.Button(prompt_buttons, text="Copiar prompt", command=self._copy_prompt)
        copy_prompt_button.pack(side='left', padx=2)
        ToolTip(copy_prompt_button, "Copia el prompt seleccionado al portapapeles.")
        open_attachment_button = ttk.Button(prompt_buttons, text="Abrir carpeta del adjunto",
                                            command=self._open_attachment_folder)
        open_attachment_button.pack(side='left', padx=2)
        ToolTip(open_attachment_button, "Abre la carpeta del archivo que debes adjuntar en el chat (modos 'pdf' e 'image').")
        continuation_button = ttk.Button(prompt_buttons, text="Copiar petición de continuación",
                                         command=self._copy_continuation)
        continuation_button.pack(side='left', padx=2)
        ToolTip(continuation_button, "Copia un mensaje para pedir más preguntas (o terminar una respuesta cortada) "
                                     "en un bloque JSON nuevo y completo.")
        ttk.Label(prompt_frame, textvariable=self.info_var, foreground="#444444", wraplength=480,
                  justify='left').pack(fill='x', padx=5, pady=(0, 5))
        panes.add(prompt_frame, weight=1)

        response_frame = ttk.LabelFrame(panes, text="2. Respuesta del chat: pégala aquí")
        self.response_text = scrolledtext.ScrolledText(response_frame, wrap=tk.WORD, height=18)
        self.response_text.pack(fill='both', expand=True, padx=5, pady=5)
        self.response_text.bind("<<Modified>>", self._on_response_modified)
        response_buttons = ttk.Frame(response_frame)
        response_buttons.pack(fill='x', padx=5, pady=(0, 5))
        paste_button = ttk.Button(response_buttons, text="Pegar del portapapeles", command=self._paste_response)
        paste_button.pack(side='left', padx=2)
        ToolTip(paste_button, "Añade el contenido del portapapeles al final de la respuesta (puedes pegar varias "
                              "respuestas seguidas, p. ej. tras pedir que continúe).")
        load_button = ttk.Button(response_buttons, text="Cargar desde archivo...", command=self._load_response_file)
        load_button.pack(side='left', padx=2)
        ToolTip(load_button, "Añade el contenido de un archivo .txt/.md/.json con la respuesta.")
        check_button = ttk.Button(response_buttons, text="Comprobar respuesta", command=self._check_response)
        check_button.pack(side='left', padx=2)
        ToolTip(check_button, "Analiza la respuesta pegada y muestra cuántas preguntas válidas contiene.")
        clear_button = ttk.Button(response_buttons, text="Borrar", command=self._clear_response)
        clear_button.pack(side='left', padx=2)
        panes.add(response_frame, weight=1)

        bottom = ttk.Frame(self)
        bottom.pack(fill='x', padx=10, pady=(5, 10))
        export_button = ttk.Button(bottom, text="Exportar prompts y respuestas (Excel + TXT)...", command=self._export_prompts)
        export_button.pack(side='left', padx=2)
        ToolTip(export_button, "Guarda los prompts (y las respuestas ya pegadas) en un Excel y en archivos .txt para "
                               "trabajar más tarde. Luego usa 'Importar respuestas desde Excel de prompts...'.")
        save_button = ttk.Button(bottom, text="3. Guardar preguntas (Excel + DOCX)", command=self._save_questions)
        save_button.pack(side='right', padx=2)
        ToolTip(save_button, "Analiza todas las respuestas, aplica el filtro de similitud y guarda los archivos "
                             "'*_pendiente_de_revisar' (igual que la generación con API).")
        ttk.Button(bottom, text="Cerrar", command=self._on_close).pack(side='right', padx=2)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _status(self, message: str) -> None:
        if self.status_callback is not None:
            self.status_callback(message)

    def _target_key(self) -> str:
        for key, spec in PROVIDERS.items():
            if spec.chat_name == self.target_var.get():
                return key
        return "gemini"

    def _set_clipboard(self, text: str) -> None:
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()  # Keeps the clipboard content available to other applications.

    def _store_current_response(self) -> None:
        if self.current_index is None:
            return
        text = self.response_text.get("1.0", tk.END).strip()
        if text:
            self.responses[self.current_index] = text
        else:
            self.responses.pop(self.current_index, None)

    def _attachments(self, index: int):
        raw = str(self.prompts_df.loc[index].get("Adjuntar", "") or "")
        return [path for path in raw.split("; ") if path]

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------
    def _on_target_change(self, event=None) -> None:
        self.tip_var.set(f"{_TARGET_TIPS[self._target_key()]}\n{_COMMON_TIP}")

    def _on_select(self, event=None) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        self._store_current_response()
        index = int(selection[0])
        self.current_index = index
        row = self.prompts_df.loc[index]

        self.prompt_text.config(state='normal')
        self.prompt_text.delete("1.0", tk.END)
        self.prompt_text.insert("1.0", str(row.get("Prompt", "")))
        self.prompt_text.config(state='disabled')

        self.response_text.delete("1.0", tk.END)
        self.response_text.insert("1.0", self.responses.get(index, ""))
        self.response_text.edit_modified(False)

        attachments = self._attachments(index)
        info = f"Tema: {row.get('Tema', '')} · {row.get('Páginas', '')} · {row.get('Caracteres', '')} caracteres."
        if attachments:
            info += " ADJUNTA en el chat: " + ", ".join(attachments)
        self.info_var.set(info)

    def _on_response_modified(self, event=None) -> None:
        if self.response_text.edit_modified():
            self.saved = False
            self.response_text.edit_modified(False)

    def _open_chat(self) -> None:
        url = PROVIDERS[self._target_key()].chat_url
        try:
            webbrowser.open_new_tab(url)
            self._status(f"Abriendo {url}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir el navegador: {e}", parent=self)

    def _copy_schema(self) -> None:
        self._set_clipboard(json.dumps(QUESTIONS_JSON_SCHEMA, ensure_ascii=False, indent=2))
        self._status("Esquema JSON copiado al portapapeles.")

    def _copy_prompt(self) -> None:
        if self.current_index is None:
            return
        prompt = str(self.prompts_df.loc[self.current_index].get("Prompt", ""))
        self._set_clipboard(prompt)
        attachments = self._attachments(self.current_index)
        message = f"Prompt {self.current_index + 1} copiado ({len(prompt)} caracteres)."
        if attachments:
            message += " Recuerda adjuntar: " + ", ".join(os.path.basename(p) for p in attachments)
        self._status(message)
        if self.current_index not in self.responses:
            self.tree.set(str(self.current_index), "estado", "Prompt copiado")

    def _open_attachment_folder(self) -> None:
        if self.current_index is None:
            return
        attachments = self._attachments(self.current_index)
        if not attachments:
            messagebox.showinfo("Sin adjuntos", "Este prompt no necesita adjuntar archivos: el texto ya está incluido.",
                                parent=self)
            return
        folder = os.path.dirname(os.path.abspath(attachments[0]))
        try:
            _open_path(folder)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir la carpeta '{folder}': {e}", parent=self)

    def _copy_continuation(self) -> None:
        text = (
            f"Genera {self.questions_per_prompt} preguntas más sobre el mismo material, distintas de las anteriores, "
            "con las mismas reglas y las mismas claves. Si tu respuesta anterior se cortó, completa primero las "
            "preguntas que faltaban. Responde ÚNICAMENTE con un NUEVO bloque de código ```json que contenga un "
            "array JSON completo e independiente, sin texto adicional."
        )
        self._set_clipboard(text)
        self._status("Petición de continuación copiada al portapapeles.")

    def _paste_response(self) -> None:
        try:
            text = self.clipboard_get()
        except tk.TclError:
            messagebox.showwarning("Portapapeles vacío", "No hay texto en el portapapeles.", parent=self)
            return
        current = self.response_text.get("1.0", tk.END).strip()
        if current:
            self.response_text.insert(tk.END, "\n\n")
        self.response_text.insert(tk.END, text)
        self._check_response(show_message=False)

    def _load_response_file(self) -> None:
        path = filedialog.askopenfilename(
            parent=self, title="Cargar respuesta del chat",
            filetypes=[("Texto", "*.txt *.md *.json"), ("Todos los archivos", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                text = f.read()
        except (OSError, UnicodeDecodeError) as e:
            messagebox.showerror("Error", f"No se pudo leer el archivo: {e}", parent=self)
            return
        if self.response_text.get("1.0", tk.END).strip():
            self.response_text.insert(tk.END, "\n\n")
        self.response_text.insert(tk.END, text)
        self._check_response(show_message=False)

    def _clear_response(self) -> None:
        self.response_text.delete("1.0", tk.END)
        if self.current_index is not None:
            self.responses.pop(self.current_index, None)
            self.tree.set(str(self.current_index), "estado", "Pendiente")

    def _check_response(self, show_message: bool = True) -> None:
        if self.current_index is None:
            return
        self._store_current_response()
        text = self.responses.get(self.current_index, "")
        questions, errors = parse_questions_response(text)
        state = f"{len(questions)} válidas" + (f", {len(errors)} no válidas" if errors else "")
        if not text:
            state = "Pendiente"
        elif not questions and not errors:
            state = "Sin preguntas reconocibles"
        self.tree.set(str(self.current_index), "estado", state)
        self._status(f"Respuesta {self.current_index + 1}: {state}.")
        if show_message:
            details = ""
            if errors:
                details = "\n\nNo válidas:\n" + "\n".join(f"• {e['Motivo']}" for e in errors[:10])
            if not questions and not errors and text:
                details = ("\n\nNo se encontró JSON con preguntas. Comprueba que has copiado la respuesta completa "
                           "(incluido el bloque ```json).")
            messagebox.showinfo("Comprobación", f"Preguntas válidas: {len(questions)}{details}", parent=self)

    def _export_prompts(self) -> None:
        self._store_current_response()
        responses = [self.responses.get(index) for index in range(len(self.prompts_df))]
        try:
            paths = self.generator.export_prompts(self.prompts_df, self.output_dir, self.output_filename,
                                                  responses=responses)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudieron exportar los prompts: {e}", parent=self)
            return
        messagebox.showinfo("Prompts exportados",
                            f"Excel: {paths['xlsx']}\nCarpeta de prompts .txt: {paths['folder']}\n\n"
                            "Pega las respuestas en la columna 'Respuesta' y usa 'Importar respuestas desde "
                            "Excel de prompts...' en la pestaña Generar Preguntas.", parent=self)

    def _save_questions(self) -> None:
        self._store_current_response()
        if not self.responses:
            messagebox.showwarning("Sin respuestas", "Pega al menos una respuesta del chat antes de guardar.", parent=self)
            return
        missing = len(self.prompts_df) - len(self.responses)
        if missing and not messagebox.askyesno(
                "Respuestas pendientes",
                f"Hay {missing} prompt(s) sin respuesta. ¿Guardar las preguntas de las respuestas disponibles?",
                parent=self):
            return

        responses = [
            {"Tema": self.prompts_df.loc[index].get("Tema", ""), "Respuesta": text}
            for index, text in sorted(self.responses.items())
        ]
        try:
            df = self.generator.import_questions_from_responses(
                responses,
                output_filename=self.output_filename,
                output_dir=self.output_dir,
                existing_bank_path=self.existing_bank_path,
                similarity_threshold=self.similarity_threshold,
            )
        except Exception as e:
            messagebox.showerror("Error", f"No se pudieron guardar las preguntas: {e}", parent=self)
            return
        self.saved = True
        paths = "\n".join(self.generator.last_output_paths.values())
        self._status(f"Preguntas sin API guardadas: {len(df)}.")
        messagebox.showinfo(
            "Preguntas guardadas",
            f"Preguntas aceptadas: {len(df)}\n"
            f"Descartadas por similitud con el banco: {len(self.generator.rejected_questions_list)}\n"
            f"Fragmentos no válidos: {len(self.generator.invalid_questions_list)}"
            + (f"\n\nArchivos guardados:\n{paths}" if paths else ""),
            parent=self,
        )

    def _on_close(self) -> None:
        self._store_current_response()
        if self.responses and not self.saved and not messagebox.askyesno(
                "Cerrar", "Hay respuestas pegadas que no se han guardado. ¿Cerrar de todos modos?", parent=self):
            return
        self.destroy()
