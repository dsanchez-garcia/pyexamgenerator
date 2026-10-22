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


def test_api_key_placeholder_is_never_saved(app, tmp_path):
    """SEC-3: el marcador 'TU_CLAVE_API' del campo se podía guardar como si fuera una clave."""
    app.api_key_var.set("TU_CLAVE_API")
    app.save_current_api_key()

    assert not (tmp_path / "config.json").exists()
    assert [kind for kind, _title, _message in app.shown_messages] == ["error"]


def test_api_key_is_saved_trimmed_with_a_single_confirmation(app, tmp_path):
    app.api_key_var.set("  clave-de-prueba  ")
    app.save_current_api_key()

    assert json.loads((tmp_path / "config.json").read_text(encoding="utf-8")) == {"api_key": "clave-de-prueba"}
    assert [kind for kind, _title, _message in app.shown_messages] == ["info"]
    assert app.load_api_key() == "clave-de-prueba"


def test_saved_placeholder_from_older_versions_is_ignored(app, tmp_path):
    (tmp_path / "config.json").write_text(json.dumps({"api_key": "TU_CLAVE_API"}), encoding="utf-8")

    assert app.load_api_key() is None


def test_selecting_source_files_twice_keeps_a_valid_list(app, tmp_path, monkeypatch):
    """GUI-4: la segunda selección se pegaba a la primera sin separador ('a.pdfb.pdf') y la coma
    separaba nombres de fichero que contienen comas."""
    from tkinter import filedialog

    first = str(tmp_path / "Calidad, Seguridad.pdf")
    second = str(tmp_path / "tema 2.pdf")
    for path in (first, second):
        open(path, "wb").close()

    monkeypatch.setattr(filedialog, "askopenfilenames", lambda **kwargs: (first,))
    app.select_pdf_files()
    monkeypatch.setattr(filedialog, "askopenfilenames", lambda **kwargs: (first, second))
    app.select_pdf_files()
    monkeypatch.setattr(filedialog, "askopenfilenames", lambda **kwargs: ())
    app.select_pdf_files()  # cancelled dialog: the list is kept

    assert app._split_paths(app.pdf_files_var.get()) == [first, second]


def test_split_paths_accepts_a_comma_list_typed_by_hand(app, tmp_path):
    a, b = str(tmp_path / "a.pdf"), str(tmp_path / "b.pdf")
    for path in (a, b):
        open(path, "wb").close()

    assert app._split_paths(f"{a}, {b}") == [a, b]
    assert app._split_paths(f"{a};{b}") == [a, b]


def test_invalid_final_grade_weight_shows_an_error(app, tmp_path):
    """GUI-5: un peso no numérico lanzaba ValueError fuera de cualquier try (solo salía por consola)."""
    app.grad_out_var.set(str(tmp_path))
    app.grad_final_mode_var.set("by_file")
    app.grad_final_files_var.set(f"{tmp_path / 'notas.xlsx'}|cuarenta")

    app.run_final_grade()

    assert [kind for kind, _title, _message in app.shown_messages] == ["error"]
    assert "cuarenta" in app.shown_messages[0][2]


def test_unreadable_bank_when_listing_topics_shows_an_error(app, tmp_path):
    """GUI-5: un banco inexistente o bloqueado por Excel solo daba un error en la consola."""
    assert app._read_bank_with_topics(str(tmp_path / "no_existe.xlsx")) is None
    assert [kind for kind, _title, _message in app.shown_messages] == ["error"]
