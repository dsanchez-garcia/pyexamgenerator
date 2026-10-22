"""Pruebas de humo de la GUI: construyen la ventana real de `ExamApp` sin mostrarla.

Necesitan una pantalla para Tk; donde no la hay (p. ej. CI en Linux) se saltan.
"""

import json
from types import SimpleNamespace

import pytest

tk = pytest.importorskip("tkinter")
from tkinter import messagebox, ttk  # noqa: E402

from pyexamgenerator import credentials, gui_logic  # noqa: E402


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

    assert credentials.get_saved_api_key() is None
    assert not (tmp_path / "config.json").exists()
    assert [kind for kind, _title, _message in app.shown_messages] == ["error"]


def test_api_key_is_saved_encrypted_with_a_single_confirmation(app, tmp_path, memory_keyring):
    """SEC-3: «Guardar Clave» la escribía sin cifrar en config.json de la carpeta actual."""
    app.api_key_var.set("  clave-de-prueba  ")
    app.save_current_api_key()

    assert memory_keyring.passwords == {("pyexamgenerator", "gemini_api_key"): "clave-de-prueba"}
    assert not (tmp_path / "config.json").exists()
    assert [(kind, "cifrada" in message) for kind, _title, message in app.shown_messages] == [("info", True)]
    assert app.api_key == "clave-de-prueba"


def test_saved_placeholder_from_older_versions_is_ignored(app, tmp_path):
    (tmp_path / "config.json").write_text(json.dumps({"api_key": "TU_CLAVE_API"}), encoding="utf-8")

    app._offer_legacy_key_migration()

    assert app.shown_messages == []
    assert (tmp_path / "config.json").exists()


def test_unencrypted_key_from_older_versions_is_moved_to_the_store(app, tmp_path):
    """SEC-3: al arrancar se ofrece mover la clave de un config.json antiguo al almacén y borrarlo."""
    (tmp_path / "config.json").write_text(json.dumps({"api_key": "clave-antigua"}), encoding="utf-8")

    app._offer_legacy_key_migration()  # askyesno answers "yes" in these tests

    assert credentials.get_saved_api_key() == "clave-antigua"
    assert not (tmp_path / "config.json").exists()
    assert (app.api_key, app.api_key_var.get()) == ("clave-antigua", "clave-antigua")
    assert [kind for kind, _title, _message in app.shown_messages] == ["info"]


def test_declined_move_keeps_the_old_file_and_uses_its_key(app, tmp_path, monkeypatch):
    (tmp_path / "config.json").write_text(json.dumps({"api_key": "clave-antigua"}), encoding="utf-8")
    monkeypatch.setattr(messagebox, "askyesno", lambda *args, **kwargs: False)

    app._offer_legacy_key_migration()

    assert credentials.get_saved_api_key() is None
    assert (tmp_path / "config.json").exists()
    assert app.api_key == "clave-antigua"


def test_old_copy_is_deleted_when_a_key_is_already_saved(app, tmp_path):
    credentials.save_api_key("clave-actual")
    (tmp_path / "config.json").write_text(json.dumps({"api_key": "clave-antigua"}), encoding="utf-8")

    app._offer_legacy_key_migration()

    assert credentials.get_saved_api_key() == "clave-actual"
    assert not (tmp_path / "config.json").exists()


def test_saved_api_key_can_be_deleted(app):
    credentials.save_api_key("clave-guardada")
    app.api_key_var.set("clave-guardada")

    app.delete_saved_api_key()

    assert credentials.get_saved_api_key() is None
    assert app.api_key_var.get() == "TU_CLAVE_API"
    assert [kind for kind, _title, _message in app.shown_messages] == ["info"]


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

    assert gui_logic.split_paths(app.pdf_files_var.get()) == [first, second]


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


def test_only_one_grading_job_runs_at_a_time(app):
    """GUI-3: dos clics seguidos lanzaban dos correcciones a la vez sobre la misma carpeta."""
    import threading

    started, release = threading.Event(), threading.Event()
    steps = []

    def slow_job():
        started.set()
        release.wait(timeout=10)
        return "hecho"

    def drive():
        # Runs inside mainloop: the worker thread can only talk to Tk while it is running.
        if not steps:
            app._grad_run_async("Trabajando", slow_job)
            steps.append("first")
        elif steps == ["first"] and started.is_set():
            app._grad_run_async("Otra vez", lambda: "no debería ejecutarse")
            steps.append("second")
            release.set()
        elif steps == ["first", "second"] and not app._grad_job_running:
            app.root.quit()
            return
        app.root.after(20, drive)

    app.root.after(0, drive)
    watchdog = app.root.after(15000, app.root.quit)  # never hang the test run
    app.root.mainloop()
    app.root.after_cancel(watchdog)

    assert steps == ["first", "second"]
    assert [kind for kind, _title, _message in app.shown_messages].count("warning") == 1
    assert ("info", "Corrección", "hecho") in app.shown_messages
    assert not app._grad_job_running


def _run_in_mainloop(app, action, done=None, timeout_ms=15000):
    """Calls ``action`` inside mainloop and keeps it running until ``done()`` is true (by default,
    until the grading job ends).

    Worker threads talk to Tk with ``root.after``, which only works while mainloop is running.
    """
    if done is None:
        def done():
            return not getattr(app, "_grad_job_running", False)

    def poll():
        if done():
            app.root.quit()
        else:
            app.root.after(20, poll)

    def start():
        action()
        poll()

    app.root.after(0, start)
    watchdog = app.root.after(timeout_ms, app.root.quit)  # never hang the test run
    app.root.mainloop()
    app.root.after_cancel(watchdog)


@pytest.fixture
def grading_backend(app, tmp_path, monkeypatch):
    """Grading inputs filled in and the grading library replaced by fakes (no files are read)."""
    import threading

    import pyexamgenerator.grading as grading
    from pyexamgenerator.grading import EnrollmentMerger, ExamCorrectionAPI

    calls = {}
    # Every Tk variable read from a thread other than the main one is recorded (GUI-2).
    reads_outside_main_thread = []
    for cls in (tk.Variable, tk.StringVar, tk.IntVar, tk.DoubleVar, tk.BooleanVar):
        original = cls.__dict__.get("get")
        if original is None:
            continue

        def checked_get(self, _original=original):
            if threading.current_thread() is not threading.main_thread():
                reads_outside_main_thread.append(str(self))
            return _original(self)

        monkeypatch.setattr(cls, "get", checked_get)

    def fake(name, result=None):
        def method(self, cfg, *args, **kwargs):
            calls[name] = cfg
            progress = kwargs.get("progress_callback")
            if progress is not None:
                progress("paso simulado")
            return result

        return method

    summary = {"changed_cells": 0, "changed_students": 0, "added": 0, "removed": 0}
    for name in ("grade_from_images", "grade_from_excel", "process_absence_justifications",
                 "integrate_ocr_grades", "apply_theory_bonus", "compute_final_grade", "run_full_pipeline"):
        monkeypatch.setattr(ExamCorrectionAPI, name, fake(name))
    monkeypatch.setattr(ExamCorrectionAPI, "compare_results",
                        fake("compare_results", SimpleNamespace(summary=summary)))
    monkeypatch.setattr(EnrollmentMerger, "export", lambda self, path: calls.setdefault("merged", path))
    monkeypatch.setattr(grading, "HAS_OCR", True)
    monkeypatch.setattr(app, "_open_folder", lambda path: calls.setdefault("opened", path), raising=False)

    out = str(tmp_path / "salida")
    for var, value in [
        (app.grad_enrollment_var, "matricula_GIM.xlsx"), (app.grad_xmls_var, "examen_1A.xml"),
        (app.grad_images_var, "hoja1.jpg;hoja2.jpg"), (app.grad_answers_var, "respuestas.xlsx"),
        (app.grad_theory_var, "teoria.xlsx"), (app.grad_attendance_var, "asistencias.xlsx"),
        (app.grad_schedule_var, "horario.xlsx"), (app.grad_justif_var, "justificaciones.xlsx"),
        (app.grad_quizzes_var, "cuestionarios.xlsx"), (app.grad_out_var, out),
        (app.grad_final_files_var, "notas.xlsx|1"), (app.grad_cmp_existing_var, "antes.xlsx"),
        (app.grad_cmp_new_var, "despues.xlsx"), (app.grad_forced_var, "hoja2.jpg=1B"),
    ]:
        var.set(value)
    return SimpleNamespace(calls=calls, reads_outside_main_thread=reads_outside_main_thread, out=out)


GRADING_ACTIONS = [
    ("grade_exams_from_images", "grade_from_images"),
    ("grade_exams_from_answers", "grade_from_excel"),
    ("run_attendance_analysis", "process_absence_justifications"),
    ("run_integrate_grades", "integrate_ocr_grades"),
    ("run_apply_bonus", "apply_theory_bonus"),
    ("run_final_grade", "compute_final_grade"),
    ("run_compare_results", "compare_results"),
    ("run_grading", "run_full_pipeline"),
]


def test_grading_jobs_read_tk_variables_only_in_the_main_thread(app, grading_backend):
    """GUI-2: los hilos de corrección leían variables Tk (`*_var.get()`), lo que no es seguro."""
    for action, library_call in GRADING_ACTIONS:  # one window for all: building it is slow
        app.shown_messages.clear()
        method = getattr(app, action)
        _run_in_mainloop(app, (lambda: method(False)) if action == "run_compare_results" else method)

        assert library_call in grading_backend.calls, action
        assert grading_backend.reads_outside_main_thread == [], action
        assert [kind for kind, _title, _message in app.shown_messages] == ["info"], action


def test_full_pipeline_button_uses_the_library_pipeline(app, grading_backend):
    """GUI-7: «Pipeline completo» delega en `ExamCorrectionAPI.run_full_pipeline`."""
    app.grad_att_header_var.set("4")

    _run_in_mainloop(app, app.run_grading)

    cfg = grading_backend.calls["run_full_pipeline"]
    assert cfg.output_dir == grading_backend.out
    assert cfg.image_paths == ["hoja1.jpg", "hoja2.jpg"]
    assert cfg.forced_type_by_image == {"hoja2.jpg": "1B"}
    assert cfg.attendance_header_row == 4
    assert grading_backend.calls["opened"] == grading_backend.out
    assert app.status_text.get() == "Corrección completada."


def test_tooltips_add_a_single_handler_to_their_window(tk_root):
    """GUI-8: cada tooltip enlazaba <Unmap>/<Destroy> en la ventana, y esos manejadores se ejecutan
    con los eventos de todos los widgets de la ventana (cambiar de pestaña, cerrar)."""
    from pyexamgenerator.tooltip import ToolTip

    window = tk.Toplevel(tk_root)
    try:
        labels = [ttk.Label(window, text=f"Campo {i}") for i in range(30)]
        tooltips = [ToolTip(label, text=f"Ayuda {i}") for i, label in enumerate(labels)]

        for sequence in ("<Unmap>", "<Destroy>"):
            handlers = [line for line in window.bind(sequence).splitlines() if line.strip()]
            assert len(handlers) == 1

        tooltips[3].showtip()
        assert tooltips[3].tipwindow is not None
        labels[5].event_generate("<Unmap>")  # another widget hidden: the tooltip stays
        assert tooltips[3].tipwindow is not None
        window.event_generate("<Unmap>")  # the window hidden: the tooltip goes away
        assert tooltips[3].tipwindow is None
    finally:
        window.destroy()


def test_question_generation_runs_in_the_background(app, monkeypatch, tmp_path):
    """GUI-3: la generación con Gemini bloqueaba la ventana hasta terminar (minutos)."""
    import threading

    import pandas as pd

    import pyexamgenerator.main_app as main_app

    release = threading.Event()
    seen = {}

    class FakeQuestionGenerator:
        def __init__(self, api_key, model_name):
            seen["model"] = model_name

        def generate_multiple_choice_questions(self, **kwargs):
            seen["thread"] = threading.current_thread()
            release.wait(timeout=10)
            return pd.DataFrame({"Pregunta": ["¿Primera?", "¿Segunda?"]})

    monkeypatch.setattr(main_app, "QuestionGenerator", FakeQuestionGenerator)
    app.api_key_var.set("clave-de-prueba")
    app.selected_model_var.set("models/gemini-de-prueba")
    app.pdf_files_var.set(str(tmp_path / "tema1.pdf"))
    button_states = []

    def while_generating():
        # The window keeps processing events while Gemini works, with the button disabled.
        button_states.append(str(app.generate_questions_button.cget("state")))
        release.set()

    def start():
        app.generate_questions()
        app.root.after(50, while_generating)

    _run_in_mainloop(app, start, done=lambda: bool(app.shown_messages))

    assert seen["model"] == "models/gemini-de-prueba"
    assert seen["thread"] is not threading.main_thread()
    assert button_states == ["disabled"]
    assert str(app.generate_questions_button.cget("state")) == "normal"
    assert app.shown_messages == [("info", "Éxito", "Preguntas generadas y guardadas (2 en total).")]


def test_rejected_gemini_request_is_shown_with_its_own_title(app, monkeypatch, tmp_path):
    """ARC-11/PKG-8: una clave no válida o un modelo retirado se explican en un diálogo propio."""
    import pyexamgenerator.main_app as main_app
    from pyexamgenerator import GeminiRequestError

    class RetiredModelGenerator:
        def __init__(self, api_key, model_name):
            pass

        def generate_multiple_choice_questions(self, **kwargs):
            raise GeminiRequestError("El modelo 'models/viejo' no existe o ya no está disponible (Error 404).")

    monkeypatch.setattr(main_app, "QuestionGenerator", RetiredModelGenerator)
    app.api_key_var.set("clave-de-prueba")
    app.selected_model_var.set("models/viejo")
    app.pdf_files_var.set(str(tmp_path / "tema1.pdf"))

    _run_in_mainloop(app, app.generate_questions, done=lambda: bool(app.shown_messages))

    assert app.shown_messages == [("error", "Error de la API de Gemini",
                                   "El modelo 'models/viejo' no existe o ya no está disponible (Error 404).")]
    assert str(app.generate_questions_button.cget("state")) == "normal"


def test_model_list_is_loaded_in_the_background(app, monkeypatch):
    """GUI-3: «Cargar Modelos» esperaba a la red con la ventana congelada."""
    import threading

    import pyexamgenerator.main_app as main_app

    seen = {}

    class FakeClient:
        def __init__(self, api_key):
            self.models = self

        def list(self):
            seen["thread"] = threading.current_thread()
            return [
                SimpleNamespace(name="models/gemini-de-prueba", display_name="Gemini de prueba", version="1",
                                input_token_limit=1000, output_token_limit=100, description="Línea 1\nLínea 2"),
                SimpleNamespace(name="models/otro-modelo"),
            ]

    monkeypatch.setattr(main_app.genai, "Client", FakeClient)
    app.api_key_var.set("clave-de-prueba")

    _run_in_mainloop(app, app.populate_models_table,
                     done=lambda: str(app.load_models_button.cget("state")) == "normal")

    assert seen["thread"] is not threading.main_thread()
    rows = [app.models_tree.item(item, "values") for item in app.models_tree.get_children()]
    assert [row[0] for row in rows] == ["models/gemini-de-prueba"]
    assert rows[0][-1] == "Línea 1 Línea 2"
    assert app.status_text.get().startswith("Se cargaron 1 modelos")


def test_exam_generation_runs_in_the_background_and_asks_in_the_main_thread(app, monkeypatch, tmp_path):
    """GUI-3: la generación de exámenes bloqueaba la ventana; la alerta de uso de preguntas, que se
    pide desde el hilo de trabajo, debe mostrarse en el hilo principal."""
    import threading

    import pandas as pd

    import pyexamgenerator.main_app as main_app

    seen = {}

    class FakeExamGenerator:
        generation_cancelled = False

        def generate_exam_from_excel(self, **kwargs):
            seen["thread"] = threading.current_thread()
            seen["answer"] = kwargs["usage_warning_callback"](pd.DataFrame(), 3, "Hay preguntas muy usadas.")
            self.generation_cancelled = not seen["answer"]

    def askyesno(title, message, **kwargs):
        seen["dialog_thread"] = threading.current_thread()
        return False  # the user cancels the generation

    monkeypatch.setattr(main_app, "ExamGenerator", FakeExamGenerator)
    monkeypatch.setattr(messagebox, "askyesno", askyesno)
    bank = tmp_path / "banco.xlsx"
    pd.DataFrame({"Tema": ["Tema 01"], "Pregunta": ["¿?"]}).to_excel(bank, index=False)
    app.excel_filepath.set(str(bank))
    app.selection_method_var.set("diccionario")
    app.questions_per_topic.set("Tema 01:1")
    app.usage_alert_enabled_var.set(True)

    _run_in_mainloop(app, app.generate_exams, done=lambda: bool(app.shown_messages))

    assert seen["thread"] is not threading.main_thread()
    assert seen["dialog_thread"] is threading.main_thread()
    assert seen["answer"] is False
    assert app.shown_messages == [
        ("info", "Cancelado", "Generacion de examenes cancelada por la alerta de uso de preguntas.")
    ]
    assert str(app.generate_exams_button.cget("state")) == "normal"


def test_mouse_wheel_scrolls_tables_and_text_boxes_inside_the_tabs(app):
    """GUI-6: la rueda del ratón se enlazaba a todos los widgets de la pestaña con "break", así que
    la tabla de modelos, el texto del prompt y la tabla de exámenes no se desplazaban."""
    for widget in (app.models_tree, app.prompt_text_display, app.update_exams_tree):
        assert widget.bind("<MouseWheel>") == ""
        assert widget.bind("<Button-4>") == ""

    # The rest of the tab still scrolls the page from any widget.
    assert app.pdf_entry.bind("<MouseWheel>") != ""


def _page_widgets(widget, self_scrolling):
    """The widgets under ``widget`` that should scroll the page: not tables, text boxes or their content."""
    for child in widget.winfo_children():
        if isinstance(child, self_scrolling):
            continue
        yield child
        yield from _page_widgets(child, self_scrolling)


def test_mouse_wheel_scrolls_every_tab_from_any_field(app):
    """ARC-2: cada pestaña montaba su propio scroll; en «Generar Exámenes» y «Corregir Exámenes» la
    rueda solo movía la página sobre el fondo, no con el ratón encima de un campo o una etiqueta."""
    for tab_id in app.notebook.tabs():
        name = app.notebook.tab(tab_id, "text")
        tab = app.root.nametowidget(tab_id)
        page = next(w for w in tab.winfo_children() if isinstance(w, tk.Canvas))
        widgets = [page, *_page_widgets(page, app._SELF_SCROLLING_WIDGETS)]
        assert any(isinstance(w, ttk.Entry) for w in widgets), name
        for event in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            unbound = [str(w) for w in widgets if not w.bind(event)]
            assert not unbound, f"{name} {event}: {unbound[:3]}"


def test_topics_load_although_a_question_has_no_topic(app, tmp_path):
    """ARC-9: una celda de `Tema` vacía (NaN) hacía fallar la ordenación y la lista de temas
    para «Seleccionar cantidad por tema» salía vacía, con el error solo en la consola."""
    import pandas as pd

    bank = tmp_path / "banco.xlsx"
    pd.DataFrame({"Pregunta": ["p1", "p2", "p3", "p4"], "Tema": ["Tema 02", None, "Tema 01", 3]}).to_excel(bank, index=False)
    app.excel_filepath.set(str(bank))

    app.load_themes_for_selection()

    assert list(app.theme_quantity_widgets) == [3, "Tema 01", "Tema 02"]


@pytest.mark.parametrize("problem", ["missing", "no_topic_column"])
def test_bank_problems_when_loading_topics_are_shown(app, tmp_path, problem):
    """ARC-9: si el banco no existe o no tiene la columna `Tema`, el aviso solo iba a la consola."""
    import pandas as pd

    bank = tmp_path / "banco.xlsx"
    if problem == "no_topic_column":
        pd.DataFrame({"Pregunta": ["p1"]}).to_excel(bank, index=False)
    app.excel_filepath.set(str(bank))

    app.load_themes_for_selection()

    shown = [w.cget("text") for w in _descendants(app.by_theme_frame) if isinstance(w, ttk.Label)]
    expected = "No se encuentra" if problem == "missing" else "columna 'Tema'"
    assert app.theme_quantity_widgets == {}
    assert any(expected in text for text in shown), shown
    assert expected in app.status_text.get()


def test_exam_template_and_grading_session_round_trip(app, tmp_path, monkeypatch):
    """ARC-2: guardar y cargar repetían a mano la lista de campos; un campo nuevo podía quedarse fuera."""
    monkeypatch.delenv("APPDATA", raising=False)  # template next to the CWD (tmp_path)
    values = [
        (app.subject, "Física"), (app.num_exams, "3"), (app.penalty, "-1/3"), (app.font_size, "12"),
        (app.export_moodle, True), (app.usage_alert_threshold_var, "4"),
        (app.grad_enrollment_var, "matricula.xlsx"), (app.grad_quizzes_var, "cuestionarios.xlsx"),
        (app.grad_cmp_new_var, "nuevo.xlsx"), (app.grad_id_col_var, "DNI"), (app.grad_append_unmatched_var, False),
    ]
    for var, value in values:
        var.set(value)
    app.grad_session_path_var.set(str(tmp_path / "sesion.json"))

    app.save_exam_tab_template()
    app.save_grading_session()
    for var, value in values:
        var.set((not value) if isinstance(value, bool) else "")
    app.load_exam_tab_template()
    app.load_grading_session()

    assert [var.get() for var, _ in values] == [value for _, value in values]


def test_exam_tab_starts_without_sample_values(app):
    """GUI-10: «Asignatura de Prueba», «Prueba GUI»... venían rellenos y acababan en exámenes reales
    (p. ej. «Prueba GUI» como instrucciones de la hoja de respuestas y en la categoría de Moodle)."""
    for var in (app.excel_filepath, app.subject, app.exam_name, app.course,
                app.answer_sheet_instructions, app.xml_cat_additional_text):
        assert var.get() == ""
    assert app.output_filename_var.get() == "preguntas"

    app.generate_exams()

    assert app.shown_messages == [("error", "Error", "Selecciona el archivo Excel del banco de preguntas.")]


def test_exam_list_shows_usage_columns_through_the_public_api(app, monkeypatch):
    """GUI-10: la GUI llamaba al método privado `_usage_column_name` del gestor del banco."""
    from pyexamgenerator.question_bank_manager import QuestionBankManager

    def private_helper(*args, **kwargs):
        raise AssertionError("la GUI no debe usar el método privado")

    monkeypatch.setattr(QuestionBankManager, "_usage_column_name", private_helper)
    app.update_exam_specs = [{"path": "examen_Evaluación_1A_completo.xlsx", "label": "Evaluación 1"}]

    app._refresh_update_exams_tree()

    values = [app.update_exams_tree.item(item, "values") for item in app.update_exams_tree.get_children()]
    assert values == [("examen_Evaluación_1A_completo.xlsx", "Evaluación 1", "Evaluacion_1_uso")]


def test_standard_messageboxes_are_not_replaced_for_the_whole_process(app):
    """GUI-9: ExamApp sustituía `tkinter.messagebox.show*` para todo el proceso (también para
    cualquier otro código Tk); ahora solo los diálogos de la aplicación usan la versión copiable."""
    import pyexamgenerator.main_app as main_app

    assert messagebox.showinfo.__module__ == "tkinter.messagebox"
    main_app.messagebox.showwarning("Aviso", "Texto que se puede copiar")
    assert app.shown_messages == [("warning", "Aviso", "Texto que se puede copiar")]


def test_exams_generated_without_updating_the_bank_show_a_warning(app, monkeypatch, tmp_path):
    """ARC-9: si el uso no se podía guardar en el banco (abierto en Excel), la GUI decía «Exámenes
    generados correctamente» y el error solo salía en la consola."""
    import pandas as pd

    import pyexamgenerator.main_app as main_app

    class LockedBankGenerator:
        generation_cancelled = False
        bank_update_error = None

        def generate_exam_from_excel(self, **kwargs):
            self.bank_update_error = "PermissionError: el fichero está abierto en Excel"

    monkeypatch.setattr(main_app, "ExamGenerator", LockedBankGenerator)
    bank = tmp_path / "banco.xlsx"
    pd.DataFrame({"Tema": ["Tema 01"], "Pregunta": ["¿?"]}).to_excel(bank, index=False)
    app.excel_filepath.set(str(bank))
    app.selection_method_var.set("diccionario")
    app.questions_per_topic.set("Tema 01:1")
    app.update_excel.set(True)

    _run_in_mainloop(app, app.generate_exams, done=lambda: bool(app.shown_messages))

    (kind, title, message), = app.shown_messages
    assert (kind, title) == ("warning", "Banco sin actualizar")
    assert "abierto en Excel" in message and "Actualizar Banco con Exámenes" in message
