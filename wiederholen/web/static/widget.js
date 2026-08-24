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
    --gew-bg: #ffffff;
    --gew-choice-bg: #ffffff;
    --gew-primary: #2563eb;
    --gew-correct: #16a34a;
    --gew-wrong: #dc2626;
    /* Sizing, not just color, is a custom property too — a host page can
       override --gew-max-width/--gew-height (custom properties inherit
       through the Shadow DOM boundary even though ordinary properties
       don't) to make the same component read as a small embedded aside on
       a landing page (the default here) or a full standalone practice
       screen on its own dedicated page, without forking the component or
       reaching inside its shadow tree. */
    --gew-max-width: 28rem;
    --gew-height: 16rem;
    display: block;
    font-family: system-ui, sans-serif;
    color: var(--gew-fg);
    max-width: var(--gew-max-width);
  }
  /* Following the OS/browser preference directly, not something read off
     the host page: the host (this project's own landing pages) has no
     manual light/dark toggle of its own either, just this same media
     query, so the two can never disagree in practice — and the Shadow DOM
     boundary doesn't affect prefers-color-scheme at all, since it's an
     environment feature, not something host-page CSS could leak through
     even without encapsulation. Every color below is redefined here rather
     than left to inherit from the host page's own --bg/--text (or similar)
     custom properties, since the widget must render sanely on a page it
     knows nothing about, dark-mode-aware or not. */
  @media (prefers-color-scheme: dark) {
    :host {
      --gew-fg: #e5e7eb;
      --gew-muted: #9ca3af;
      --gew-border: #3f3f46;
      --gew-bg: #18181b;
      --gew-choice-bg: #27272a;
      --gew-primary: #3b82f6;
      --gew-correct: #4ade80;
      --gew-wrong: #f87171;
    }
  }
  .widget {
    border: 1px solid var(--gew-border);
    border-radius: 0.5rem;
    padding: 1rem;
    /* Explicit, not left transparent: without this, the widget's own text
       color (--gew-fg) rendered straight onto whatever the host page's
       background happened to be — invisible dark-on-dark text on a page
       using prefers-color-scheme: dark, since only the border/text colors
       were ever theme-aware, not the widget's own backing surface. */
    background: var(--gew-bg);
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
    height: var(--gew-height);
    overflow: hidden;
    display: flex;
    flex-direction: column;
    /* A guaranteed gap between .body and the toolbar after it (the answer
       control or "Next" button) — without this, that boundary had no
       spacing of its own at all, only whatever margin the last paragraph
       inside .body happened to carry (the default p { margin-bottom:
       0.75rem }, or nothing for a toolbar-only state like .centered).
       .question's/.description's own margin: auto (see their comments)
       distribute space *within* .body proportionally to how much slack
       there is, which is exactly right for them — but that system has
       nothing to do with the .body-to-toolbar boundary, so pairing it with
       only a 0.75rem paragraph margin there reads as an afterthought next
       to the much more generous auto-computed gaps above it (caught from
       a real screenshot: description sat nearly flush against the answer
       input). A fixed gap here is deliberately simple rather than trying
       to make this boundary participate in the same auto-margin math. */
    gap: 1rem;
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
    display: flex;
    flex-direction: column;
    /* One consistent 1rem rhythm for every boundary in the card — this gap
       between whichever of instruction/question/description are actually
       present, matching .widget's own gap (above) between .body and the
       toolbar after it. flexbox's gap only inserts space *between* items
       that actually exist, so a topic with no instruction (or no
       description — both are independently optional per exercise, see
       CLAUDE.md) never leaves a phantom empty gap where it would've been:
       there's simply one fewer boundary to space. An earlier version tried
       to get this same top-fixed/center/bottom-pinned shape from
       margin: auto (see .question's git history) — mathematically correct,
       but its gaps scaled with the leftover space in a way that visually
       came out uneven, and it needed a *separate*, disconnected fixed gap
       glued on for the .body-to-toolbar boundary alone (which this system
       makes redundant, since that boundary now uses the exact same
       mechanism). */
    gap: 1rem;
    /* A soft fade at the very bottom edge, not a hard cutoff — hints that
       there's more to scroll to on narrow viewports especially (a long
       German sentence wraps to more lines there, more easily filling
       .body's fixed height than on a wider desktop embed). mask-image
       fades this element's own content toward transparent, revealing
       whatever's actually behind it, so it works regardless of the site's
       (or dark mode's) actual background color — no color to keep in sync.
       A fixed, deliberately small fade zone (calc(100% - 0.35rem)), not a
       percentage of .body's own height: a percentage-based zone (the
       original design) scales with .body's height rather than with the
       text it's fading — harmless for most content, which (like .centered-pair
       below) has centering slack around it and never touches the fade
       zone at all, but the standalone app's taller --gew-height card
       (see CLAUDE.md's "Web frontend") could still turn it into most of
       a line reading visibly faded on whichever content ends up flush
       against .body's bottom edge — e.g. a genuinely long instruction
       pushing .centered-pair down far enough to fill the rest of .body outright, or
       .body's own scroll kicking in (caught from a real screenshot, back
       when .description itself sat flush against .body's bottom by
       design instead of inside .centered-pair). A small fixed zone keeps the
       softening to what it was always meant to be regardless: a few
       pixels of a line's own bottom edge, not the line itself. */
    mask-image: linear-gradient(to bottom, black calc(100% - 0.35rem), transparent 100%);
  }
  p { margin: 0; line-height: 1.4; }
  .muted { color: var(--gew-muted); }
  .instruction { font-size: 0.9em; color: var(--gew-muted); }
  /* .centered-pair groups a card's two central pieces of text into one
     visual unit that moves and centers together, rather than leaving the
     second one to drift off on its own: on the question screen that's
     .question + .description (a translation of .question into the
     student's language reads as a mirror of it, one line down in a
     quieter voice, not a separate fact); on the result screen it's the
     ✅/❌ label + explanation (the verdict, and the grammar note backing
     it up). flex: 1 is the *only* growable item in .body's column
     (instruction, when present, stays sized to its own content), so
     .centered-pair claims 100% of whatever vertical space it doesn't
     need, and this nested flex column centers the pair as a group within
     whatever it claimed — instead of the pair packing at the top of the
     card with a dead gap below it before the toolbar, reported from real
     screenshots on *both* screens (the question one first, then the
     result one once the same imbalance was noticed there too). gap:
     0.5rem inside the pair is deliberately *tighter* than .body's own
     1rem rhythm elsewhere (see below) — that larger interval separates
     genuinely distinct pieces of the card, while this smaller one is
     what visually reads as one connected thought rather than two
     unrelated lines. text-align: center here, not repeated on each
     child, covers both children by inheritance. On the rare case long
     enough to actually need .body's own scroll, flex: 1 still can't
     shrink the pair below its content's natural height, so it just packs
     at the top like a plain paragraph would — no worse than top-
     alignment already was, unlike plain justify-content: center on .body
     itself would have been (that can push a flex group's start past the
     scrollable area's top edge on overflow, making the beginning of the
     text unreachable by scrolling — the same pitfall .centered avoids
     for the same reason elsewhere). An earlier version kept .question
     and .description independent, .description pinned to the bottom of
     .body on its own (first via margin-top/margin-bottom: auto on
     .question mirrored by margin-top: auto on .description, later via
     flex: 1 on .question alone) — mathematically sound either way, but
     it left .description visually stranded far from .question with no
     sense that the two were related at all, regardless of description's
     own alignment (centering it in that far-away position was tried and
     reverted for the same reason — caught from real user reports both
     times). Grouping them under one flex: 1 replaced all of that with a
     single rule that already produces an even rhythm and a real visual
     pairing, with no piece bolted on separately. */
  .centered-pair {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    text-align: center;
  }
  .question { font-size: 1.1em; font-weight: 600; }
  /* font-size: 1.1em matches .question — on the result screen, this
     label (the ✅/❌ verdict plus, when wrong, the correct answer itself)
     plays .question's role in its own .centered-pair with .explanation
     (below): it's the actual fact worth remembering, so it gets the same
     visual weight .question gets on the question screen, not a
     shrunken-down status tag. See .explanation's own comment. */
  .correct { color: var(--gew-correct); font-weight: 600; font-size: 1.1em; }
  .wrong { color: var(--gew-wrong); font-weight: 600; font-size: 1.1em; }
  /* .explanation plays .description's role in its own .centered-pair
     with the ✅/❌ label (above) on the result screen — the supporting
     grammar note under the answer that actually matters, styled exactly
     like .description for the same reason: smaller and muted, visually
     secondary to the label next to it. Sharing .description's own rule
     (rather than a separate one with the same values) keeps the "smaller
     secondary text in a pair" look defined in one place. */
  .description, .explanation { font-size: 0.9em; color: var(--gew-muted); }
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
    /* color: inherit isn't the default for form controls (button/input
       have their own UA-stylesheet color, not "inherit"), so without this
       both would silently keep light-mode-appropriate black text even
       once --gew-fg switches for dark mode. */
    color: inherit;
    background: var(--gew-choice-bg);
  }
  button { cursor: pointer; }
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

// The exercise's own content (question/description/instruction/explanation)
// is already localized server-side via the `language` request param — this
// is just the widget's own fixed chrome (buttons, error/empty-state text)
// around it, which the server never sees and has no way to translate. "en"
// is included even though it duplicates the English literals that used to
// be inline, so a topic/language combination the API doesn't recognize
// still degrades to a real language rather than a KeyError.
const STRINGS = {
  ru: {
    nothingAvailable: "Пока нечего тренировать — загляните позже!",
    somethingWrong: "Что-то пошло не так.",
    tryAgain: "Попробовать снова",
    next: "Дальше",
    correct: "Верно!",
    correctAnswer: (answer) => `Правильный ответ: ${answer}`,
  },
  en: {
    nothingAvailable: "Nothing to practice here right now — come back later!",
    somethingWrong: "Something went wrong.",
    tryAgain: "Try again",
    next: "Next",
    correct: "Correct!",
    correctAnswer: (answer) => `Correct answer: ${answer}`,
  },
};

class GermanExerciseWidget extends HTMLElement {
  constructor() {
    super();
    this._shadow = this.attachShadow({ mode: "open" });
    // Bound once so add/removeEventListener refer to the same function.
    this._onViewportResize = this._onViewportResize.bind(this);
  }

  connectedCallback() {
    // Reuse whatever question was already showing before a plain page
    // reload, instead of always spending a fresh /api/exercise/next call —
    // the server's own session (WebSessionStore's shown_exercise) hasn't
    // moved on either, since only actually submitting an answer does that,
    // so re-rendering the cached DTO is exactly consistent with what the
    // backend still thinks is "shown" for this student.
    const cached = this._readCachedExercise();
    if (cached) {
      this._renderQuestion(cached);
    } else {
      this._loadNext();
    }
    // visualViewport, not the input's own focus event: the on-screen
    // keyboard's height isn't known yet at the moment focus fires, only
    // once it's actually finished opening — which is exactly when
    // visualViewport fires its own resize. Optional chaining, since
    // visualViewport isn't universally available; on a browser without it
    // this degrades to the native scroll-to-input behavior the issue this
    // fixes was filed against, not a crash.
    window.visualViewport?.addEventListener("resize", this._onViewportResize);
  }

  disconnectedCallback() {
    window.visualViewport?.removeEventListener(
      "resize",
      this._onViewportResize
    );
  }

  _onViewportResize() {
    // this._shadow.activeElement, not a reference captured at render time:
    // _render() replaces the whole shadow subtree (and thus the <input>
    // itself) on every step, and this listener is only ever attached once
    // for the element's whole lifetime — a stale reference to an already-
    // replaced <input> would never match. Only scrolls for the typed-answer
    // input specifically (the only <input> this widget ever renders) — a
    // resize while a choice button is focused, say, needs no correction,
    // since tapping a button doesn't open the keyboard in the first place.
    if (this._shadow.activeElement?.tagName === "INPUT") {
      this.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }

  // sessionStorage, not localStorage: it survives a reload of this same tab
  // (the actual complaint this caches against) but clears once the tab/
  // session ends, so a genuinely new visit just gets a fresh question
  // without needing any separate expiry bookkeeping here — that alone
  // roughly tracks WebSessionStore's own 1h TTL for the common case of
  // reloading soon after the page was first opened. If the two ever do
  // drift apart (tab left open past that hour, then answered), check_answer
  // 409s and the learner sees the existing error+retry path, not a crash.
  get _cacheKey() {
    return `wiederholen-widget:${this._topics.join(",")}:${this._language}`;
  }

  _readCachedExercise() {
    const raw = sessionStorage.getItem(this._cacheKey);
    if (!raw) return null;
    try {
      return JSON.parse(raw);
    } catch {
      return null;
    }
  }

  _writeCachedExercise(exercise) {
    sessionStorage.setItem(this._cacheKey, JSON.stringify(exercise));
  }

  _clearCachedExercise() {
    sessionStorage.removeItem(this._cacheKey);
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

  // Falls back to ru, not en, for an unrecognized lang attribute — matches
  // _language's own default above, so the two stay consistent rather than
  // disagreeing about which language an unset/unsupported attribute means.
  get _strings() {
    return STRINGS[this._language] || STRINGS.ru;
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

  // focusOnLoad distinguishes "this render is a direct response to the
  // learner tapping something" (Next, Retry — where autofocusing the typed-
  // answer input, and the mobile keyboard that comes with it, is expected)
  // from a cold connectedCallback() render, where it isn't: popping the
  // keyboard open the instant the page loads, before the learner has done
  // anything at all, was a real complaint from a real mobile screenshot.
  async _loadNext(focusOnLoad = false) {
    this._renderLoading();
    try {
      const exercise = await this._post("/api/exercise/next", {
        topics: this._topics,
        language: this._language,
      });
      if (exercise === null) {
        this._clearCachedExercise();
        this._render(
          `<div class="widget centered"><p class="muted">${escapeHtml(this._strings.nothingAvailable)}</p></div>`
        );
        return;
      }
      this._writeCachedExercise(exercise);
      this._renderQuestion(exercise, focusOnLoad);
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
      // The just-answered exercise is no longer "pending" — a reload right
      // now must not resurrect it from cache and let it be answered again,
      // so this clears before rendering the result rather than only when
      // the learner actually clicks "Next" afterward.
      this._clearCachedExercise();
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
      `<div class="widget centered"><p class="wrong">${escapeHtml(this._strings.somethingWrong)}</p>` +
        `<button data-retry>${escapeHtml(this._strings.tryAgain)}</button></div>`
    );
    this._shadow
      .querySelector("[data-retry]")
      .addEventListener("click", () => this._loadNext(true));
  }

  _renderQuestion(exercise, focusOnLoad = false) {
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
      // instruction, then .centered-pair (question + description
      // together) — not source order — so instruction always sits at the
      // same fixed spot regardless of whether a given exercise has a
      // description at all. question and description are wrapped
      // together so they move and center as one unit — description (a
      // translation of question, not an instruction on how to answer)
      // reads as question's own mirror, one line down in a quieter
      // voice, not a footnote adrift at the bottom of the card. See
      // .centered-pair's own comment for the reasoning.
      `<div class="widget"><div class="body">${instruction}` +
        `<div class="centered-pair"><p class="question">❓ ${escapeHtml(exercise.question)}</p>` +
        `${description}</div></div>` +
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
      // Gated on focusOnLoad, though: on mobile, focusing a text input pops
      // the on-screen keyboard open immediately — welcome right after the
      // learner taps "Next"/"Try again", but not the instant the page
      // itself finishes loading, before they've done anything at all
      // (caught from a real mobile report).
      if (focusOnLoad) {
        input.focus({ preventScroll: true });
      }
    }
  }

  _renderResult(result) {
    const label = result.correct
      ? `<p class="correct">✅ ${escapeHtml(this._strings.correct)}</p>`
      : `<p class="wrong">❌ ${escapeHtml(this._strings.correctAnswer(result.answer))}</p>`;
    this._render(
      // label + explanation share one .centered-pair, the same treatment
      // question + description get on the question screen: the verdict
      // (and, when wrong, the correct answer itself) is the actual fact
      // worth remembering, so it plays .question's role, and the grammar
      // note backing it up plays .description's — see .explanation's own
      // comment for the reasoning, and .centered-pair's for why grouping
      // beats leaving the two as independent top-packed siblings.
      `<div class="widget"><div class="body">` +
        `<div class="centered-pair">${label}` +
        `<p class="explanation">${escapeHtml(result.explanation)}</p></div></div>` +
        `<button data-next>${escapeHtml(this._strings.next)}</button></div>`
    );
    const nextButton = this._shadow.querySelector("[data-next]");
    nextButton.addEventListener("click", () => this._loadNext(true));
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
