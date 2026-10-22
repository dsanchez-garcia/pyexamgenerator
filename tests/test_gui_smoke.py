"""Pruebas de humo de la GUI: construyen la ventana real de `ExamApp` sin mostrarla.

Necesitan una pantalla para Tk; donde no la hay (p. ej. CI en Linux) se saltan.
"""

import json
from types import SimpleNamespace

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


def _run_in_mainloop(app, action, timeout_ms=15000):
    """Calls ``action`` inside mainloop and keeps it running until the grading job ends.

    Worker threads talk to Tk with ``root.after``, which only works while mainloop is running.
    """

    def poll():
        if getattr(app, "_grad_job_running", False):
            app.root.after(20, poll)
        else:
            app.root.quit()

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
