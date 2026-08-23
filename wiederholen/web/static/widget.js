// <german-exercise-widget topics="partizip_ii,praeteritum" lang="ru"></german-exercise-widget>
//
// A Web Component, no build step, no dependencies. Renders into a Shadow
// DOM so a landing page's own CSS can never leak in (or be leaked onto) —
// see CLAUDE.md's "Web frontend" section for the reasoning behind this and
// the API it talks to.
//
// `api-base` defaults to the origin this very script was loaded from
// (captured once, below, while `document.currentScript` is still valid —
// it stops being usable the moment this file finishes its first pass, long
// before any instance's connectedCallback() runs), so a page only needs to
// repeat the API domain explicitly if the widget is served from somewhere
// else entirely.
const _SCRIPT_SRC = document.currentScript ? document.currentScript.src : null;

const STYLES = `
  :host {
    --gew-fg: #1a1a1a;
    --gew-muted: #6b7280;
    --gew-border: #d1d5db;
    --gew-primary: #2563eb;
    --gew-correct: #16a34a;
    --gew-wrong: #dc2626;
    display: block;
    font-family: system-ui, sans-serif;
    color: var(--gew-fg);
    max-width: 28rem;
  }
  .widget {
    border: 1px solid var(--gew-border);
    border-radius: 0.5rem;
    padding: 1rem;
    box-sizing: border-box;
    /* A fixed height, not just a floor: real questions vary a lot in size
       (a description/instruction line or not, one choice row or two, a
       short vs. long explanation), and a min-height alone still let the
       widget resize between every step — still jolting the surrounding
       page, just less often. A fixed height stops that outright. overflow
       is hidden here, not scrollable — .body below is the one thing that
       scrolls internally; see its own comment for why that split exists.
       Sized to comfortably fit the common case (description + instruction
       + question + a wrapped choices row) without .body needing to scroll
       on a typical desktop-width embed — narrower viewports need more of
       it (the same German sentence wraps to more lines at, say, 350px than
       at 450px), so this is intentionally a bit taller than the bare
       desktop minimum rather than exactly it. */
    height: 16rem;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }
  /* Short, single-purpose states (a loading placeholder, an error, "nothing
     available") — centering them in the fixed-height box reads as an
     intentional state screen rather than a stray line stuck at the top of a
     mostly-empty box. Not applied to .widget generally: a real question or
     result's content should start from the top like normal reading order. */
  .widget.centered {
    align-items: center;
    justify-content: center;
    text-align: center;
  }
  /* The question/result states each wrap their variable-length content (the
     description/instruction/question, or the label/explanation) in .body,
     leaving the answer control (.choices/the typed-input form) or the
     "Next" button as a plain sibling after it — a toolbar that's never part
     of the scrolling region. flex: 1 makes .body claim all the vertical
     space the toolbar doesn't need, which is also what pins a short
     toolbar to the bottom of the fixed-height box without a separate
     margin-top: auto rule (an earlier version of this used exactly that,
     directly on the toolbar element — it visually anchored the toolbar
     correctly, but .widget's own overflow-y: auto still scrolled the
     *entire* box including the toolbar for a too-long question, taking the
     answer control out of view along with it). min-height: 0 overrides a
     flex item's default min-height: auto, which would otherwise keep .body
     at its content's full height and defeat overflow-y: auto entirely —
     a well-known flexbox-plus-scrolling gotcha, not a redundant rule. */
  .widget .body {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    /* A soft fade at the very bottom edge, not a hard cutoff — hints that
       there's more to scroll to on narrow viewports especially (a long
       German sentence wraps to more lines there, more easily filling
       .body's fixed height than on a wider desktop embed). mask-image
       fades this element's own content toward transparent, revealing
       whatever's actually behind it, so it works regardless of the site's
       (or dark mode's) actual background color — no color to keep in sync.
       Harmless when content already fits without scrolling: at most it
       softens the last few pixels of the final line, which reads as
       intentional rather than a visible bug either way. */
    mask-image: linear-gradient(to bottom, black 92%, transparent 100%);
  }
  p { margin: 0 0 0.75rem; line-height: 1.4; }
  .muted { color: var(--gew-muted); }
  .description, .instruction { font-size: 0.9em; color: var(--gew-muted); }
  .question { font-size: 1.1em; font-weight: 600; }
  .correct { color: var(--gew-correct); font-weight: 600; }
  .wrong { color: var(--gew-wrong); font-weight: 600; }
  /* grid, not flex-wrap: flex-wrap sizes each button to its own text,
     leaving column edges ragged whenever one choice is longer than its
     neighbor (e.g. "mein Wunsch" next to "meines Wunsches") — grid's equal-
     width columns (and its default stretch, which fills each button to its
     own cell) keep every button in a row the same width and every column
     aligned, however uneven the choice text lengths are. A fixed 2 columns,
     not auto-fit: nearly every real exercise has exactly 4 choices (345 of
     346 in the actual course data), and auto-fit sized to a minmax(7rem,
     1fr) track sometimes decided 3 columns fit the widget's own width —
     leaving the 4th choice stranded alone on its own row instead of the
     clean 2x2 that 4 choices in a fixed 2-column grid always gives. */
  .choices {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 0.5rem;
  }
  button, input[type="text"] {
    font: inherit;
    border-radius: 0.375rem;
    border: 1px solid var(--gew-border);
    padding: 0.5rem 0.75rem;
  }
  button { cursor: pointer; background: white; }
  button:hover { border-color: var(--gew-primary); }
  button[data-next], button[type="submit"] {
    background: var(--gew-primary);
    color: white;
    border-color: var(--gew-primary);
  }
  form { display: flex; gap: 0.5rem; }
  input[type="text"] { flex: 1; }
`;

function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value;
  return div.innerHTML;
}

class GermanExerciseWidget extends HTMLElement {
  constructor() {
    super();
    this._shadow = this.attachShadow({ mode: "open" });
  }

  connectedCallback() {
    this._loadNext();
  }

  get _topics() {
    return (this.getAttribute("topics") || "")
      .split(",")
      .map((topic) => topic.trim())
      .filter(Boolean);
  }

  get _language() {
    return this.getAttribute("lang") || "ru";
  }

  get _apiBase() {
    const explicit = this.getAttribute("api-base");
    if (explicit) return explicit.replace(/\/$/, "");
    return _SCRIPT_SRC ? new URL(_SCRIPT_SRC).origin : "";
  }

  async _post(path, body) {
    const response = await fetch(`${this._apiBase}${path}`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      throw new Error(`${path} responded ${response.status}`);
    }
    return response.json();
  }

  async _loadNext() {
    this._renderLoading();
    try {
      const exercise = await this._post("/api/exercise/next", {
        topics: this._topics,
        language: this._language,
      });
      if (exercise === null) {
        this._render(
          `<div class="widget centered"><p class="muted">Nothing to practice here right now — come back later!</p></div>`
        );
        return;
      }
      this._renderQuestion(exercise);
    } catch {
      this._renderError();
    }
  }

  async _submitAnswer(answer) {
    this._renderLoading();
    try {
      const result = await this._post("/api/exercise/check", {
        answer,
        language: this._language,
      });
      this._renderResult(result);
    } catch {
      this._renderError();
    }
  }

  _renderLoading() {
    this._render(`<div class="widget centered"><p class="muted">…</p></div>`);
  }

  _renderError() {
    this._render(
      `<div class="widget centered"><p class="wrong">Something went wrong.</p>` +
        `<button data-retry>Try again</button></div>`
    );
    this._shadow
      .querySelector("[data-retry]")
      .addEventListener("click", () => this._loadNext());
  }

  _renderQuestion(exercise) {
    const description = exercise.description
      ? `<p class="description">💭 ${escapeHtml(exercise.description)}</p>`
      : "";
    const instruction = exercise.instruction
      ? `<p class="instruction">ℹ️ ${escapeHtml(exercise.instruction)}</p>`
      : "";
    const answerArea = exercise.choices
      ? `<div class="choices">${exercise.choices
          .map((choice) => `<button data-choice>${escapeHtml(choice)}</button>`)
          .join("")}</div>`
      : `<form data-answer-form>` +
        `<input type="text" autocomplete="off" />` +
        `<button type="submit">✓</button></form>`;
    this._render(
      `<div class="widget"><div class="body">${description}${instruction}` +
        `<p class="question">❓ ${escapeHtml(exercise.question)}</p></div>` +
        `${answerArea}</div>`
    );
    this._shadow.querySelectorAll("[data-choice]").forEach((button) => {
      button.addEventListener("click", () =>
        this._submitAnswer(button.textContent)
      );
    });
    const form = this._shadow.querySelector("[data-answer-form]");
    if (form) {
      const input = form.querySelector("input");
      form.addEventListener("submit", (event) => {
        event.preventDefault();
        this._submitAnswer(input.value);
      });
      // Same reasoning as _renderResult()'s Next-button focus: _render()
      // just wiped whatever had focus (e.g. the previous question's Next
      // button), so without this the learner has to click the input by
      // hand before they can type — breaking a keyboard-only flow right
      // where it matters most. preventScroll: true, since .focus()'s
      // default scroll-into-view behavior would otherwise yank the whole
      // page down to the widget the moment it loads on a page where it
      // isn't already at the top (e.g. embedded partway down a landing
      // page) — jarring on first load, and not something a learner who's
      // already looking at the widget needs on every subsequent question.
      input.focus({ preventScroll: true });
    }
  }

  _renderResult(result) {
    const label = result.correct
      ? `<p class="correct">✅ Correct!</p>`
      : `<p class="wrong">❌ Correct answer: ${escapeHtml(result.answer)}</p>`;
    this._render(
      `<div class="widget"><div class="body">${label}` +
        `<p>${escapeHtml(result.explanation)}</p></div>` +
        `<button data-next>Next</button></div>`
    );
    const nextButton = this._shadow.querySelector("[data-next]");
    nextButton.addEventListener("click", () => this._loadNext());
    // Re-rendering (_render() replaces the whole shadow subtree) drops
    // whatever had focus before this answer was submitted, so the page's
    // focus falls back to <body> — a keydown there never reaches this
    // element's shadow tree. Focusing the button directly sidesteps that:
    // a focused <button> already activates on Enter per native browser
    // behavior, no separate keyboard handling needed. preventScroll: true
    // for the same reason as _renderQuestion()'s input — the widget is
    // already in view by the time an answer's been submitted, so there's
    // nothing to scroll to, but no reason to risk it either.
    nextButton.focus({ preventScroll: true });
  }

  _render(html) {
    this._shadow.innerHTML = `<style>${STYLES}</style>${html}`;
  }
}

customElements.define("german-exercise-widget", GermanExerciseWidget);
