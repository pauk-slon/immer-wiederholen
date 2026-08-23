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
  }
  p { margin: 0 0 0.75rem; line-height: 1.4; }
  .muted { color: var(--gew-muted); }
  .description, .instruction { font-size: 0.9em; color: var(--gew-muted); }
  .question { font-size: 1.1em; font-weight: 600; }
  .correct { color: var(--gew-correct); font-weight: 600; }
  .wrong { color: var(--gew-wrong); font-weight: 600; }
  .choices { display: flex; flex-wrap: wrap; gap: 0.5rem; }
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
    this._render(`<div class="widget"><p class="muted">…</p></div>`);
    try {
      const exercise = await this._post("/api/exercise/next", {
        topics: this._topics,
        language: this._language,
      });
      if (exercise === null) {
        this._render(
          `<div class="widget"><p class="muted">Nothing to practice here right now — come back later!</p></div>`
        );
        return;
      }
      this._renderQuestion(exercise);
    } catch {
      this._renderError();
    }
  }

  async _submitAnswer(answer) {
    this._render(`<div class="widget"><p class="muted">…</p></div>`);
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

  _renderError() {
    this._render(
      `<div class="widget"><p class="wrong">Something went wrong.</p>` +
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
      `<div class="widget">${description}${instruction}` +
        `<p class="question">❓ ${escapeHtml(exercise.question)}</p>` +
        `${answerArea}</div>`
    );
    this._shadow.querySelectorAll("[data-choice]").forEach((button) => {
      button.addEventListener("click", () =>
        this._submitAnswer(button.textContent)
      );
    });
    const form = this._shadow.querySelector("[data-answer-form]");
    if (form) {
      form.addEventListener("submit", (event) => {
        event.preventDefault();
        this._submitAnswer(form.querySelector("input").value);
      });
    }
  }

  _renderResult(result) {
    const label = result.correct
      ? `<p class="correct">✅ Correct!</p>`
      : `<p class="wrong">❌ Correct answer: ${escapeHtml(result.answer)}</p>`;
    this._render(
      `<div class="widget">${label}` +
        `<p>${escapeHtml(result.explanation)}</p>` +
        `<button data-next>Next</button></div>`
    );
    this._shadow
      .querySelector("[data-next]")
      .addEventListener("click", () => this._loadNext());
  }

  _render(html) {
    this._shadow.innerHTML = `<style>${STYLES}</style>${html}`;
  }
}

customElements.define("german-exercise-widget", GermanExerciseWidget);
