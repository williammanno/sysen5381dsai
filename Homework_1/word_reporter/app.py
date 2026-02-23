# app.py
# AI-Powered Word Pronunciation Reporter — Shiny for Python
# Queries Merriam-Webster API (with Free Dictionary fallback), word list with A–Z and length filters,
# and uses Ollama to generate pronunciation and usage insights.

import random
from datetime import datetime

from shiny import App, reactive, render, ui

from api_client import get_word_data, get_api_key
from ollama_client import (
    generate_report_docx,
    get_report_text,
    report_to_txt,
    report_to_md,
    report_to_html,
    report_to_docx_ai_only,
)
from word_list import get_all_words, filter_words, get_length_range_choices

# -----------------------------------------------------------------------------
# Custom styles
# -----------------------------------------------------------------------------

APP_CSS = """
.shiny-app .main-content { padding: 1.5rem 2rem; max-width: 900px; }
.app-header {
  background: linear-gradient(135deg, #2d6a4f 0%, #1b4332 100%);
  color: white;
  padding: 1.25rem 1.5rem;
  border-radius: 0.5rem;
  margin-bottom: 1.5rem;
  box-shadow: 0 2px 8px rgba(45, 106, 79, 0.25);
}
.app-header h2 { margin: 0; font-weight: 600; font-size: 1.5rem; }
.app-header p { margin: 0.35rem 0 0 0; opacity: 0.9; font-size: 0.95rem; }
.content-card {
  background: white;
  border-radius: 0.5rem;
  padding: 1.25rem;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
  border: 1px solid #e9ecef;
  margin-bottom: 1rem;
}
.pronunciation-row { padding: 0.4rem 0; border-bottom: 1px solid #eee; }
.pronunciation-row:last-child { border-bottom: none; }
.pronunciation-raw { font-family: 'Georgia', serif; font-size: 1.1rem; color: #1b4332; }
.pronunciation-type { font-size: 0.8rem; color: #6c757d; }
.definition-block { margin-bottom: 0.75rem; }
.definition-pos { font-weight: 600; color: #2d6a4f; font-size: 0.9rem; }
.empty-state {
  text-align: center;
  padding: 2rem;
  color: #6c757d;
  background: #f8f9fa;
  border-radius: 0.5rem;
  border: 1px dashed #dee2e6;
}
.ai-report { white-space: pre-wrap; line-height: 1.5; }
.sidebar-footer { font-size: 0.8rem; color: #6c757d; margin-top: 0.5rem; }
.audio-row { margin-bottom: 0.75rem; }
.audio-row audio { width: 100%; max-width: 280px; height: 36px; }
.word-chip { display: inline-block; margin: 2px 4px 2px 0; padding: 4px 10px; border-radius: 999px;
  background: #e8f5e9; color: #1b4332; cursor: pointer; border: 1px solid #a5d6a7; font-size: 0.9rem; }
.word-chip:hover { background: #c8e6c9; }
.word-list-wrap { max-height: 220px; overflow-y: auto; padding: 0.5rem 0; }
"""

# Preload word list and choices
_ALL_WORDS = get_all_words()
_LETTER_CHOICES = ["All"] + [chr(i) for i in range(ord("A"), ord("Z") + 1)]
_LENGTH_CHOICES = get_length_range_choices()

# -----------------------------------------------------------------------------
# UI
# -----------------------------------------------------------------------------

app_ui = ui.page_sidebar(
    ui.sidebar(
        ui.tags.div(
            ui.tags.p("Look up a word", class_="fw-semibold text-secondary small text-uppercase mb-2"),
            ui.input_text("word", "Word", value="", placeholder="e.g. pronunciation"),
            ui.tags.div(
                ui.input_action_button("fetch_btn", "Look up word", class_="btn-primary w-100"),
                class_="mt-3",
            ),
            ui.tags.hr(class_="my-3"),
            ui.tags.p("Browse & learn", class_="fw-semibold text-secondary small text-uppercase mb-2"),
            ui.input_select(
                "letter_filter",
                "Starting letter",
                choices={c: c for c in _LETTER_CHOICES},
                selected="All",
            ),
            ui.input_select(
                "length_filter",
                "Word length",
                choices={label: label for label, _ in _LENGTH_CHOICES},
                selected="Any length",
            ),
            ui.input_action_button("random_btn", "Random word", class_="btn btn-outline-success w-100 mt-2"),
            ui.tags.p("Choose a word to look up:", class_="small text-muted mt-2 mb-1"),
            ui.output_ui("word_select_ui"),
            ui.tags.hr(class_="my-3"),
            ui.tags.p(
                "Uses Merriam-Webster (key in word.env) or Free Dictionary API.",
                class_="sidebar-footer mt-3",
            ),
            class_="p-3",
        ),
        title=ui.tags.span("Word Reporter", style="font-weight: 600;"),
        bg="#f8f9fa",
        width=300,
    ),
    ui.tags.div(
        ui.tags.style(APP_CSS),
        ui.tags.div(
            ui.tags.div(
                ui.tags.h2("Pronunciation & usage", class_="mb-1"),
                ui.tags.p(
                    "Type a word, pick one from the list, or use Random word. Download an AI report as a Word document (.docx).",
                    class_="mb-0 opacity-90",
                ),
                class_="app-header",
            ),
            class_="mb-4",
        ),
        ui.output_ui("data_card"),
        class_="main-content",
    ),
    title="AI Word Pronunciation Reporter",
    fillable=True,
)

# -----------------------------------------------------------------------------
# Server
# -----------------------------------------------------------------------------


def server(input, output, session):
    word_result = reactive.value(None)
    is_loading = reactive.value(False)
    # Cache AI report text per word so we only call Ollama once when saving in multiple formats
    report_text_cache = reactive.value(None)
    report_word_cache = reactive.value(None)

    def filtered_words():
        letter_sel = input.letter_filter()
        length_sel = input.length_filter()
        min_len, max_len = None, None
        for label, (mn, mx) in _LENGTH_CHOICES:
            if label == length_sel:
                min_len, max_len = mn, mx
                break
        return filter_words(
            _ALL_WORDS,
            start_letter=letter_sel if letter_sel != "All" else None,
            min_len=min_len,
            max_len=max_len,
        )

    @render.ui
    def word_select_ui():
        words = filtered_words()
        if not words:
            return ui.tags.p("No words match the filters.", class_="small text-muted")
        choices = {w: w for w in words[:500]}
        return ui.input_select(
            "word_select",
            label=None,
            choices=choices,
            selected=None,
            selectize=True,
        )

    def do_fetch(w: str):
        """Fetch word data and set word_result."""
        is_loading.set(True)
        report_text_cache.set(None)
        report_word_cache.set(None)
        try:
            res = get_word_data(w)
            if res.get("ok"):
                res = {**res, "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M")}
            word_result.set(res)
        finally:
            is_loading.set(False)

    @reactive.effect
    @reactive.event(input.fetch_btn)
    def _fetch():
        w = (input.word() or "").strip()
        if w:
            do_fetch(w)
        else:
            word_result.set({"ok": False, "error": "Enter a word."})

    @reactive.effect
    @reactive.event(input.word_select)
    def _fetch_from_select():
        w = (input.word_select() or "").strip()
        if w:
            ui.update_text("word", value=w)
            do_fetch(w)

    @reactive.effect
    @reactive.event(input.random_btn)
    def _random_word():
        words = filtered_words()
        if not words:
            return
        w = random.choice(words)
        ui.update_text("word", value=w)
        ui.update_select("word_select", selected=w)
        do_fetch(w)

    def current_result():
        return word_result.get()

    @render.ui
    def data_card():
        if is_loading.get():
            return ui.tags.div(
                ui.tags.div(
                    ui.tags.span("Loading...", class_="text-primary fw-medium"),
                    ui.tags.div(
                        ui.tags.div(class_="spinner-border spinner-border-sm text-primary", role="status"),
                        class_="mt-2",
                    ),
                    class_="empty-state",
                ),
                class_="content-card",
            )
        res = current_result()
        if res is None:
            return ui.tags.div(
                ui.tags.div(
                    ui.tags.p('Enter a word, choose one from the list, or click "Random word" to see pronunciations.', class_="mb-0"),
                    class_="empty-state",
                ),
                class_="content-card",
            )
        if not res.get("ok"):
            return ui.tags.div(
                ui.tags.div(
                    ui.tags.strong("Error"),
                    ui.tags.p(res.get("error", "Unknown error"), class_="text-danger mb-0 mt-1 small"),
                    class_="content-card border border-danger",
                ),
            )
        word = res.get("word", "")
        prons = res.get("pronunciations", [])
        defs = res.get("definitions", [])
        audio = res.get("audio", [])
        fetched_at = res.get("fetched_at", "")

        pron_ui = []
        if prons:
            for p in prons:
                raw = p.get("raw") or "—"
                raw_type = p.get("rawType") or "—"
                pron_ui.append(
                    ui.tags.div(
                        ui.tags.span(raw, class_="pronunciation-raw"),
                        ui.tags.span(f" ({raw_type})", class_="pronunciation-type"),
                        class_="pronunciation-row",
                    )
                )
        else:
            pron_ui.append(ui.tags.p("No text pronunciations found.", class_="text-muted small mb-0"))

        # Vocal pronunciation (audio from Merriam-Webster API)
        audio_ui = []
        if audio:
            audio_ui.append(ui.tags.h6("Vocal pronunciation", class_="mt-3 mb-2"))
            for i, a in enumerate(audio):
                url = (a.get("fileUrl") or "").strip()
                if url:
                    audio_ui.append(
                        ui.tags.div(
                            ui.tags.audio(src=url, controls=True, preload="metadata"),
                            class_="audio-row",
                        )
                    )

        defs_ui = []
        if defs:
            for d in defs:
                pos = d.get("partOfSpeech") or "—"
                text = (d.get("text") or "")[:400]
                defs_ui.append(
                    ui.tags.div(
                        ui.tags.span(pos, class_="definition-pos"),
                        ui.tags.p(text, class_="mb-1 small"),
                        class_="definition-block",
                    )
                )
        else:
            defs_ui.append(ui.tags.p("No definitions found.", class_="text-muted small mb-0"))

        children = [
            ui.tags.h5(word, class_="mb-2"),
            ui.tags.span(f"Fetched {fetched_at}", class_="text-muted small"),
            ui.tags.h6("Pronunciations", class_="mt-3 mb-2"),
            ui.tags.div(*pron_ui),
        ]
        if audio_ui:
            children.extend(audio_ui)
        children.extend([
            ui.tags.h6("Definitions", class_="mt-3 mb-2"),
            ui.tags.div(*defs_ui),
        ])
        if prons or defs:
            children.append(
                ui.tags.div(
                    ui.tags.h6("Save AI report", class_="mt-3 mb-2"),
                    ui.tags.p("Full report (word data + AI summary):", class_="small text-muted mb-1"),
                    ui.download_button("download_report", "Download full report (.docx)", class_="btn btn-success btn-sm me-1 mb-1"),
                    ui.tags.p("AI report only (multiple formats):", class_="small text-muted mt-2 mb-1"),
                    ui.download_button("download_txt", ".txt", class_="btn btn-outline-secondary btn-sm me-1 mb-1"),
                    ui.download_button("download_md", ".md", class_="btn btn-outline-secondary btn-sm me-1 mb-1"),
                    ui.download_button("download_html", ".html", class_="btn btn-outline-secondary btn-sm me-1 mb-1"),
                    ui.download_button("download_docx_ai", ".docx", class_="btn btn-outline-secondary btn-sm me-1 mb-1"),
                    class_="mt-2",
                )
            )
        return ui.tags.div(*children, class_="content-card")

    def _get_cached_report_text():
        """Return (text, error) for current word; use cache or call Ollama."""
        res = current_result()
        if not res or not res.get("ok"):
            return None, (res.get("error") if res else "No word data.") or "No data"
        word = res.get("word", "")
        if report_word_cache.get() == word and report_text_cache.get():
            return report_text_cache.get(), None
        text, err = get_report_text(res)
        if not err and text:
            report_word_cache.set(word)
            report_text_cache.set(text)
        return text, err

    @render.download(filename=lambda: f"word_report_{(current_result() or {}).get('word', 'word')}.docx")
    def download_report():
        res = current_result()
        if not res or not res.get("ok"):
            return
        yield generate_report_docx(res)

    @render.download(filename=lambda: f"word_ai_report_{(current_result() or {}).get('word', 'word')}.txt")
    def download_txt():
        text, err = _get_cached_report_text()
        if err:
            yield f"Error: {err}"
            return
        yield report_to_txt(text or "")

    @render.download(filename=lambda: f"word_ai_report_{(current_result() or {}).get('word', 'word')}.md")
    def download_md():
        text, err = _get_cached_report_text()
        if err:
            yield f"Error: {err}"
            return
        yield report_to_md(text or "")

    @render.download(filename=lambda: f"word_ai_report_{(current_result() or {}).get('word', 'word')}.html")
    def download_html():
        text, err = _get_cached_report_text()
        if err:
            yield report_to_html(f"Error: {err}", title="Report Error")
            return
        yield report_to_html(text or "", title=f"Word AI Report — {(current_result() or {}).get('word', 'word')}")

    @render.download(filename=lambda: f"word_ai_report_{(current_result() or {}).get('word', 'word')}.docx")
    def download_docx_ai():
        text, err = _get_cached_report_text()
        if err:
            yield report_to_docx_ai_only(f"Error: {err}")
            return
        yield report_to_docx_ai_only(text or "")


# -----------------------------------------------------------------------------
# App
# -----------------------------------------------------------------------------

app = App(app_ui, server)