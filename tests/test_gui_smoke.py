"""Pruebas de humo de la GUI: construyen la ventana real de `ExamApp` sin mostrarla.

Necesitan una pantalla para Tk; donde no la hay (p. ej. CI en Linux) se saltan.
"""

import json

import pytest

tk = pytest.importorskip("tkinter")
from tkinter import messagebox, ttk  # noqa: E402


@pytest.fixture(scope="module")
def tk_root():
    # A single Tk interpreter per module: creating tk.Tk() repeatedly in one process fails
    # intermittently on Windows ("Can't find a usable tk.tcl").
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"No hay pantalla disponible para Tk: {exc}")
    root.withdraw()
    yield root
    root.destroy()


@pytest.fixture
def app(tk_root, tmp_path, monkeypatch):
    # Aislar de la configuración del usuario: config.json y custom_prompts.json se leen del CWD.
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    # ExamApp sustituye estos diálogos para todo el proceso; se restauran al terminar el test.
    for name in ("showinfo", "showwarning", "showerror"):
        monkeypatch.setattr(messagebox, name, getattr(messagebox, name))
    root = tk.Toplevel(tk_root)
    root.withdraw()

    from pyexamgenerator.main_app import ExamApp

    try:
        exam_app = ExamApp(root)
        # Dialogs are modal and would block the test run: record them instead.
        exam_app.shown_messages = []

        def record(kind, title=None, message=None, **_kwargs):
            exam_app.shown_messages.append((kind, title, message))

        monkeypatch.setattr(exam_app, "_show_copyable_messagebox", record)
        monkeypatch.setattr(messagebox, "askyesno", lambda *args, **kwargs: True)
        yield exam_app
    finally:
        root.destroy()


def _descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from _descendants(child)


def _last_dialog(app):
    return [w for w in app.root.winfo_children() if isinstance(w, tk.Toplevel)][-1]


def test_main_window_builds_all_tabs(app):
    tabs = {app.notebook.tab(tab_id, "text") for tab_id in app.notebook.tabs()}
    assert tabs == {"Generar Preguntas", "Gestionar Banco de Preguntas", "Generar Exámenes", "Corregir Exámenes"}


def test_edit_prompt_dialog_shows_the_existing_text(app):
    """GUI-1: «Editar» abría el diálogo con el prompt vacío (ganaba una copia duplicada del método)."""
    app.add_edit_prompt_type(existing_type="PRL")

    text_widget = next(w for w in _descendants(_last_dialog(app)) if isinstance(w, tk.Text))
    assert text_widget.get("1.0", "end-1c").strip() == app.prompt_types["PRL"].strip()


def test_renaming_a_custom_prompt_replaces_it(app, tmp_path):
    app.prompt_types["Historia"] = "Prompt de historia"
    app.add_edit_prompt_type(existing_type="Historia")
    dialog = _last_dialog(app)

    entry = next(w for w in _descendants(dialog) if isinstance(w, ttk.Entry))
    entry.delete(0, tk.END)
    entry.insert(0, "Historia moderna")
    next(w for w in _descendants(dialog) if isinstance(w, ttk.Button)).invoke()

    assert app.shown_messages == []
    assert "Historia" not in app.prompt_types
    assert app.prompt_types["Historia moderna"] == "Prompt de historia"
    saved = json.loads((tmp_path / "custom_prompts.json").read_text(encoding="utf-8"))
    assert saved == {"Historia moderna": "Prompt de historia"}
    assert app.selected_prompt_type.get() == "Historia moderna"
