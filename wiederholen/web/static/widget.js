// <german-exercise-widget topics="partizip_ii,praeteritum" lang="ru"></german-exercise-widget>
//
// A Web Component, no build step, no dependencies. Renders into a Shadow
// DOM so a landing page's own CSS can never leak in (or be leaked onto) —
// see CLAUDE.md's "Web frontend" section for the reasoning behind this and
// the API it talks to.
//
// A bare `recall` attribute opts into the recall step (off by default —
// see _recallEnabled's own comment for why a landing-page embed shouldn't
// just get it for free).
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
  /* The sized viewport: one exercise's steps (question, result, a recall
     question, a recall result, ...) are each their own separate .card (see
     below), laid out side by side in .track and clipped to one card's
     width here. Swiping/scrolling .track, or the .deck-nav arrows, moves
     between them — see CLAUDE.md's "Web frontend" section for why cards
     are separate and swipeable rather than one card growing with appended
     content (the design this replaced). */
  .deck {
    position: relative;
    width: 100%;
    height: var(--gew-height);
    overflow: hidden;
  }
  /* scroll-snap-type, not a JS-driven carousel: swipe/trackpad scrolling
     works natively, for free, and always lands cleanly on a card boundary
     — no framework, no per-frame JS. The scrollbar itself is hidden (both
     properties needed — Firefox honors the standard one, Chrome/Safari
     need the pseudo-element) since .deck-nav's arrows are the intended
     visible control, not a thin native scrollbar sitting under the cards. */
  .track {
    display: flex;
    height: 100%;
    overflow-x: auto;
    scroll-snap-type: x mandatory;
    scrollbar-width: none;
  }
  .track::-webkit-scrollbar { display: none; }
  .card {
    /* flex: 0 0 100% — exactly one card's width per "page"; stretched to
       .track's full height by flex's own default align-items: stretch, no
       explicit height needed here. scroll-snap-align: start is what makes
       a swipe/arrow-click always come to rest with a card's left edge
       flush against .deck's, rather than stopping mid-scroll between two. */
    flex: 0 0 100%;
    scroll-snap-align: start;
    border: 1px solid var(--gew-border);
    border-radius: 0.5rem;
    padding: 1rem;
    /* Explicit, not left transparent: without this, the card's own text
       color (--gew-fg) rendered straight onto whatever the host page's
       background happened to be — invisible dark-on-dark text on a page
       using prefers-color-scheme: dark, since only the border/text colors
       were ever theme-aware, not the card's own backing surface. */
    background: var(--gew-bg);
    box-sizing: border-box;
    /* overflow: hidden, not scrollable — .body below is the one thing
       that scrolls internally within a card; see its own comment for why
       that split exists. */
    overflow: hidden;
    display: flex;
    flex-direction: column;
    /* A guaranteed gap between .body and the toolbar after it (the answer
       control or "Next" button) — without this, that boundary had no
       spacing of its own at all, only whatever margin the last paragraph
       inside .body happened to carry (the default p { margin-bottom:
       0.75rem }, or nothing for a toolbar-only state like .card.centered).
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
     mostly-empty box. Not applied to .card generally: a real question or
     result's content should start from the top like normal reading order. */
  .card.centered {
    align-items: center;
    justify-content: center;
    text-align: center;
  }
  /* Small circular buttons at .deck's own left/right edges, using the
     existing --gew-* tokens so they're theme-aware for free — not a
     separate class, so .deck-nav.prev/.next only differ in which edge
     they sit on. Hidden via the plain hidden attribute (see
     _updateDeckNav()), not just visually, whenever there's nothing to
     navigate to — a fresh, not-yet-answered question is the one genuinely
     single-card state (nothing to page through yet), so both arrows stay
     hidden until the first answer; from then on the result is already a
     second card in its own right (a distinct message, not just recall's
     doing), so at least one arrow shows for the rest of the exercise. */
  .deck-nav {
    position: absolute;
    top: 50%;
    transform: translateY(-50%);
    width: 1.75rem;
    height: 1.75rem;
    border-radius: 50%;
    background: var(--gew-bg);
    color: var(--gew-fg);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1rem;
    line-height: 1;
    padding: 0;
    opacity: 0.85;
  }
  .deck-nav:hover { opacity: 1; }
  .deck-nav.prev { left: 0.5rem; }
  .deck-nav.next { right: 0.5rem; }
  /* .deck-nav's own display: flex above has the same specificity as the
     browser's built-in [hidden] { display: none } rule, and author styles
     beat the user-agent stylesheet regardless of selector order — without
     this, the hidden attribute _updateDeckNav() sets would be silently
     ineffective and both arrows would render always-visible (caught from
     a real screenshot: a "next" arrow showing on the deck's very last
     card, right where there is nothing to go next to). */
  .deck-nav[hidden] { display: none; }
  /* The question/result states each wrap their variable-length content (the
     description/instruction/question, or the label/explanation) in .body,
     leaving the answer control (.choices/the typed-input form) or the
     "Next" button as a plain sibling after it — a toolbar that's never part
     of the scrolling region. flex: 1 makes .body claim all the vertical
     space the toolbar doesn't need, which is also what pins a short
     toolbar to the bottom of the fixed-height card without a separate
     margin-top: auto rule (an earlier version of this used exactly that,
     directly on the toolbar element — it visually anchored the toolbar
     correctly, but .card's own overflow: hidden still let a too-long
     question take the answer control out of view along with it). min-height: 0 overrides a
     flex item's default min-height: auto, which would otherwise keep .body
     at its content's full height and defeat overflow-y: auto entirely —
     a well-known flexbox-plus-scrolling gotcha, not a redundant rule. */
  .card .body {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    /* One consistent 1rem rhythm for every boundary in the card — this gap
       between whichever of instruction/question/description are actually
       present, matching .card's own gap (above) between .body and the
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
       pushing .centered-pair down far enough to fill the rest of .body
       outright, or .body's own scroll kicking in (caught from a real
       screenshot, back when .description itself sat flush against
       .body's bottom by design instead of inside .centered-pair). A
       small fixed zone keeps the softening to what it was always meant
       to be regardless: a few pixels of a line's own bottom edge, not
       the line itself. */
    mask-image: linear-gradient(to bottom, black calc(100% - 0.35rem), transparent 100%);
  }
  p { margin: 0; line-height: 1.4; }
  .muted { color: var(--gew-muted); }
  .instruction { font-size: 0.9em; color: var(--gew-muted); }
  /* .centered-pair groups a card's two central pieces of text into one
     visual unit that moves and centers together, rather than leaving the
     second one to drift off on its own: on the question card that's
     .question + .description (a translation of .question into the
     student's language reads as a mirror of it, one line down in a
     quieter voice, not a separate fact); on the result card it's the
     ✅/❌ label + explanation (the verdict, and the grammar note backing
     it up); a recall card reuses .question/.description directly for its
     own question/hint, since it's every bit as much "a question, plus an
     optional note under it" as the original — now that recall gets its
     own dedicated card with its own claimed vertical space (see
     CLAUDE.md's "Web frontend"), there's no reason for it to need a
     special case of its own, unlike an earlier version of this design.
     flex: 1 is the *only* growable item in .body's column
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
     text unreachable by scrolling — the same pitfall .card.centered avoids
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
  /* font-size: 1.1em matches .question — on the result card, this
     label (the ✅/❌ verdict plus, when wrong, the correct answer itself)
     plays .question's role in its own .centered-pair with .explanation
     (below): it's the actual fact worth remembering, so it gets the same
     visual weight .question gets on the question card, not a
     shrunken-down status tag. See .explanation's own comment. */
  .correct { color: var(--gew-correct); font-weight: 600; font-size: 1.1em; }
  .wrong { color: var(--gew-wrong); font-weight: 600; font-size: 1.1em; }
  /* .explanation plays .description's role in its own .centered-pair
     with the ✅/❌ label (above) on the result card — the supporting
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
     1fr) track sometimes decided 3 columns fit the card's own width —
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
  /* The two-button toolbar shared by both recall-offer states — "Закрепить"
     (after a correct answer with recalls available) and "Попробовать ещё
     раз" (after a wrong recall attempt) — paired with "Дальше" either way,
     mirroring the bot's own _make_recall_buttons(), which always shows the
     same two side by side. Equal-width buttons via flex: 1, the same
     pattern form's own input[type="text"] already uses for its one growing
     child. */
  .actions { display: flex; gap: 0.5rem; }
  .actions button { flex: 1; }
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
    // Mirrors the bot's own l10n.py wording exactly (btn_recall,
    // btn_recall_retry, recall_correct, recall_wrong, recall_prompt) —
    // recallRetry is kept distinct from tryAgain above (a different
    // button, for the unrelated network-error-retry case) since the bot's
    // own ru copy for the two differs ("Попробовать ещё раз" vs
    // "Попробовать снова"). recallInstruction drops recall_prompt's own
    // "\n{recall}" — the widget already renders the recall question as
    // its own .question line right below, so only the framing sentence
    // itself is needed here.
    recallDrill: "Закрепить",
    recallRetry: "Попробовать ещё раз",
    recallCorrect: "Правильно!",
    recallWrong: (answer) => `Неправильно. Правильный вариант: ${answer}`,
    recallInstruction: "Восстановите фразу",
  },
  en: {
    nothingAvailable: "Nothing to practice here right now — come back later!",
    somethingWrong: "Something went wrong.",
    tryAgain: "Try again",
    next: "Next",
    correct: "Correct!",
    correctAnswer: (answer) => `Correct answer: ${answer}`,
    recallDrill: "Drill",
    recallRetry: "Try again",
    recallCorrect: "Correct!",
    recallWrong: (answer) => `Wrong. Correct answer: ${answer}`,
    recallInstruction: "Reconstruct the phrase",
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
    // both _render() (a fresh deck) and _addCard() (a fresh card within
    // the existing deck) replace/add whatever <input> was there, and this
    // listener is only ever attached once for the element's whole lifetime
    // — a stale reference to an already-replaced <input> would never
    // match. Only scrolls for the typed-answer
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

  // Off by default — a landing-page embed is meant to stay a light,
  // low-commitment sample of practicing, not the full bot-parity
  // experience; the standalone app (the one place actually working toward
  // that parity) opts in explicitly with the bare `recall` attribute, the
  // same boolean-attribute convention `disabled`/`required` use natively.
  // A single shared component with this one behavior gated, rather than a
  // second forked file, is deliberate: the two contexts already share
  // everything else (layout, sizing via --gew-*, i18n, focus handling),
  // and forking would mean applying every future fix twice.
  get _recallEnabled() {
    return this.hasAttribute("recall");
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
      // status is attached (not just embedded in the message string) so
      // _reportClientError() below can report it as a real number the
      // server can query on, not text a human has to parse back out.
      throw Object.assign(new Error(`${path} responded ${response.status}`), {
        status: response.status,
      });
    }
    return response.json();
  }

  // Best-effort, fire-and-forget: POST /api/client-error turns into
  // queryable attributes on that request's own auto-instrumented span
  // (see CLAUDE.md's "Web frontend"/"Tracing" — the same OTel/Honeycomb
  // pipeline the backend already uses, not a separate tool), so a real
  // failure shows up as more than a bare docker-logs access-log line a
  // human has to notice and manually reproduce. .catch(() => {}) here is
  // deliberate: a failure to *report* an error must never itself become a
  // new user-facing error — this call's own result is never awaited or
  // otherwise allowed to affect what the caller does next.
  _reportClientError(step, error) {
    this._post("/api/client-error", { step, status: error?.status ?? null }).catch(
      () => {}
    );
  }

  // focusOnLoad distinguishes "this render is a direct response to the
  // learner tapping something" (Next, Retry — where autofocusing the typed-
  // answer input, and the mobile keyboard that comes with it, is expected)
  // from a cold connectedCallback() render, where it isn't: popping the
  // keyboard open the instant the page loads, before the learner has done
  // anything at all, was a real complaint from a real mobile screenshot.
  async _loadNext(focusOnLoad = false) {
    // A full deck reset (not _addCard()) is correct at every branch below
    // — this is always the start of a *new* exercise, so nothing from a
    // previous one (if any) is worth keeping around to swipe back to.
    this._renderLoading();
    try {
      const exercise = await this._post("/api/exercise/next", {
        topics: this._topics,
        language: this._language,
      });
      if (exercise === null) {
        this._clearCachedExercise();
        this._render(
          `<div class="card centered"><p class="muted">${escapeHtml(this._strings.nothingAvailable)}</p></div>`
        );
        return;
      }
      this._writeCachedExercise(exercise);
      this._renderQuestion(exercise, focusOnLoad);
    } catch (error) {
      this._reportClientError("loadNext", error);
      this._renderError();
    }
  }

  async _submitAnswer(answer) {
    // A transient loading state in the *current* (question) card's own
    // toolbar, not a full _renderLoading() reset — the question stays in
    // the deck throughout, so it's still there to swipe back to once the
    // result card is added below.
    this._setToolbar(`<p class="muted">…</p>`);
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
    } catch (error) {
      this._reportClientError("submitAnswer", error);
      // Restores the question card's own toolbar to an error + "Next" —
      // deliberately *not* a retry of this same check_answer() call. A
      // real-world failure here is far more often a 409 (the server's
      // WebSessionStore session for this exercise expired — 1h TTL — while
      // sessionStorage's own cached copy, which has none, kept letting the
      // learner answer a question the backend no longer has any record of
      // showing) than a transient network blip: retrying the identical
      // request would just 409 again forever, since nothing about the
      // mismatch changes between attempts (caught from a real 409 in
      // production logs after an earlier version of this tried exactly
      // that "genuine retry"). Fetching a fresh exercise is what actually
      // recovers either way — same shape as _startRecall()'s own catch
      // (below), and this clears the stale cache outright too, so even a
      // reload before tapping "Next" won't resurrect the same doomed
      // question. Deliberately not routed through the shared, full-reset
      // _renderError() either: that's still correct for _loadNext()'s own
      // failures, but would wipe this question card here, same reasoning
      // as _startRecall()'s own catch.
      this._clearCachedExercise();
      this._setToolbar(
        `<p class="wrong">${escapeHtml(this._strings.somethingWrong)}</p>` +
          `<button data-next>${escapeHtml(this._strings.next)}</button>`
      );
      this._wireNextButton();
    }
  }

  _renderLoading() {
    this._render(`<div class="card centered"><p class="muted">…</p></div>`);
  }

  _renderError() {
    this._render(
      `<div class="card centered"><p class="wrong">${escapeHtml(this._strings.somethingWrong)}</p>` +
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
      `<div class="card"><div class="body">${instruction}` +
        `<div class="centered-pair"><p class="question">❓ ${escapeHtml(exercise.question)}</p>` +
        `${description}</div></div>` +
        `<div class="toolbar">${answerArea}</div></div>`
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
      // Same reasoning as _wireNextButton()'s own focus call: _render()
      // just wiped whatever had focus (e.g. the previous card's Next
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
    this._addCard(
      // label + explanation share one .centered-pair, the same treatment
      // question + description get on the question card: the verdict
      // (and, when wrong, the correct answer itself) is the actual fact
      // worth remembering, so it plays .question's role, and the grammar
      // note backing it up plays .description's — see .explanation's own
      // comment for the reasoning, and .centered-pair's for why grouping
      // beats leaving the two as independent top-packed siblings. An
      // empty .toolbar here — filled in just below, once recall mode is
      // known — rather than baked into this same template string, so
      // _startRecall()/etc. below can all go through the one _setToolbar()
      // path instead of a separate one just for this initial render.
      // _addCard() (not _render()) is what makes this a new card of its
      // own, freezing the question card above it rather than replacing it
      // — see CLAUDE.md's "Web frontend" section for the deck this is part
      // of.
      `<div class="card"><div class="body">` +
        `<div class="centered-pair">${label}` +
        `<p class="explanation">${escapeHtml(result.explanation)}</p></div></div>` +
        `<div class="toolbar"></div></div>`
    );
    // result.recall mirrors the bot's own RecallMode: "none" (no recalls on
    // this exercise at all — plain Next, unchanged from before recall
    // existed), "optional" (answered correctly, a recall is offered but not
    // required), "required" (answered wrong, a recall must be attempted
    // before moving on — started immediately, no offer needed since it
    // isn't optional). Forced to "none" when _recallEnabled is off (the
    // default — see its own comment), rather than a separate branch
    // duplicating "none"'s own body — an embed that never asked for recall
    // takes exactly the same path as an exercise with no recalls at all.
    const recallMode = this._recallEnabled ? result.recall : "none";
    if (recallMode === "required") {
      this._startRecall();
    } else if (recallMode === "optional") {
      this._setToolbarToActions(this._strings.recallDrill, () => this._startRecall());
    } else {
      this._setToolbar(`<button data-next>${escapeHtml(this._strings.next)}</button>`);
      this._wireNextButton();
    }
  }

  // Fetches a recall (POST /api/exercise/recall) and adds it as a brand new
  // card — never replaces what's already shown, so the just-answered
  // result stays fully intact, one swipe/arrow-click back (see CLAUDE.md's
  // "Web frontend" section for the deck this belongs to). Used both for a
  // fresh recall (called directly from _renderResult() above) and for a
  // retry after a wrong attempt (called from _submitRecallAnswer()'s own
  // wrong branch below) — either way it's a brand new recall.question/
  // hint, its own new card, which is what makes a retry read as another
  // page in the deck rather than overwriting the previous attempt.
  async _startRecall() {
    // A transient loading state in the *current* card's own toolbar — not
    // a new card yet, since there's nothing to show until the fetch
    // resolves.
    this._setToolbar(`<p class="muted">…</p>`);
    try {
      const recall = await this._post("/api/exercise/recall", {
        language: this._language,
      });
      // A recall question is still a question — reuses .question/
      // .description directly, exactly like the question card, now that
      // it gets its own dedicated card (and dedicated .centered-pair
      // space) rather than being squeezed into someone else's. .instruction
      // here plays the same role it does on the question card (a fixed
      // note on how to answer *this* step, not part of the question text
      // itself) — mirrors the bot's own recall_prompt ("Восстановите
      // фразу:") — without it, a learner had no explanation of what a
      // recall step even was or how it differs from the main exercise
      // (caught from a direct user report: the bot has this framing, the
      // widget didn't).
      const hint = recall.hint
        ? `<p class="description">💡 ${escapeHtml(recall.hint)}</p>`
        : "";
      this._addCard(
        `<div class="card"><div class="body">` +
          `<p class="instruction">ℹ️ ${escapeHtml(this._strings.recallInstruction)}</p>` +
          `<div class="centered-pair"><p class="question">❓ ${escapeHtml(recall.question)}</p>${hint}</div>` +
          `</div><div class="toolbar">` +
          `<form data-recall-form><input type="text" autocomplete="off" />` +
          `<button type="submit">✓</button></form></div></div>`
      );
      const form = this._currentCard.querySelector("[data-recall-form]");
      const input = form.querySelector("input");
      form.addEventListener("submit", (event) => {
        event.preventDefault();
        this._submitRecallAnswer(input.value);
      });
      // Not focusOnLoad-gated like _renderQuestion()'s own input: this is
      // always the direct result of a deliberate action (submitting the
      // main answer that triggered a required recall, or tapping
      // "Закрепить"/"Попробовать ещё раз"), never a cold page load — the
      // one case that gating exists to avoid (see _renderQuestion()'s own
      // comment).
      input.focus({ preventScroll: true });
    } catch (error) {
      this._reportClientError("startRecall", error);
      // Never leaves the learner stuck: restores the *current* card's own
      // toolbar to an error + a way forward, rather than adding a new
      // (empty, pointless) card for a recall that never actually arrived.
      this._setToolbar(
        `<p class="wrong">${escapeHtml(this._strings.somethingWrong)}</p>` +
          `<button data-next>${escapeHtml(this._strings.next)}</button>`
      );
      this._wireNextButton();
    }
  }

  async _submitRecallAnswer(answer) {
    this._setToolbar(`<p class="muted">…</p>`);
    try {
      const result = await this._post("/api/exercise/recall/check", { answer });
      // A new card for the verdict alone — a single-child .centered-pair
      // centers it exactly the same way a two-child one does (align-items/
      // justify-content don't care how many children there are).
      const label = result.correct
        ? `<p class="correct">✅ ${escapeHtml(this._strings.recallCorrect)}</p>`
        : `<p class="wrong">❌ ${escapeHtml(this._strings.recallWrong(result.answer))}</p>`;
      this._addCard(
        `<div class="card"><div class="body">` +
          `<div class="centered-pair">${label}</div></div>` +
          `<div class="toolbar"></div></div>`
      );
      if (result.correct) {
        this._setToolbar(`<button data-next>${escapeHtml(this._strings.next)}</button>`);
        this._wireNextButton();
      } else {
        this._setToolbarToActions(this._strings.recallRetry, () => this._startRecall());
      }
    } catch (error) {
      this._reportClientError("submitRecallAnswer", error);
      // Same reasoning as _startRecall()'s own catch: restore the current
      // card's toolbar rather than adding a new card for a result that
      // never actually arrived.
      this._setToolbar(
        `<p class="wrong">${escapeHtml(this._strings.somethingWrong)}</p>` +
          `<button data-next>${escapeHtml(this._strings.next)}</button>`
      );
      this._wireNextButton();
    }
  }

  // Shared by both recall-offer states — "Закрепить" after a correct
  // answer, "Попробовать ещё раз" after a wrong recall attempt — which
  // always pair their own trigger with a "Дальше" button, mirroring the
  // bot's own _make_recall_buttons() (always the same two-button shape,
  // just a different label on the first one).
  _setToolbarToActions(triggerLabel, onTrigger, card = this._currentCard) {
    this._setToolbar(
      `<div class="actions">` +
        `<button data-recall-trigger>${escapeHtml(triggerLabel)}</button>` +
        `<button data-next>${escapeHtml(this._strings.next)}</button></div>`,
      card
    );
    card
      .querySelector("[data-recall-trigger]")
      .addEventListener("click", onTrigger);
    this._wireNextButton(card);
  }

  // Wires whichever [data-next] button is in card's .toolbar and focuses
  // it — factored out since a fresh Next button appears in several places
  // now (the plain result card, after a correct recall, alongside a
  // recall-offer/retry button), all wanting the exact same click/focus
  // behavior. Defaults to _currentCard, but a caller that just built a
  // *specific* card (rather than relying on it already being current)
  // passes it explicitly — see _setToolbarToActions() above.
  _wireNextButton(card = this._currentCard) {
    const nextButton = card.querySelector("[data-next]");
    nextButton.addEventListener("click", () => this._loadNext(true));
    // Re-toolbaring drops whatever had focus before, so the page's focus
    // falls back to <body> — a keydown there never reaches this element's
    // shadow tree. Focusing the button directly sidesteps that: a focused
    // <button> already activates on Enter per native browser behavior, no
    // separate keyboard handling needed. preventScroll: true since the
    // card is already in view (either it's been there the whole time, or
    // _addCard() already scrolled to it) — nothing to scroll to, but no
    // reason to risk it either.
    nextButton.focus({ preventScroll: true });
  }

  // card, not just "the" toolbar: once a deck can hold several cards, a
  // bare this._shadow.querySelector(".toolbar") would match the *first*
  // one in document order, not necessarily the current one — every caller
  // above defaults to _currentCard precisely to avoid that.
  _setToolbar(html, card = this._currentCard) {
    card.querySelector(".toolbar").innerHTML = html;
  }

  // .track's last child — the newest step in the deck, and the only card
  // whose toolbar should still be a live control surface (see _addCard()).
  get _currentCard() {
    return this._shadow.querySelector(".track").lastElementChild;
  }

  // Adds a new card as a new step in the deck — unlike _render(), nothing
  // already shown is touched, which is the whole point: a learner can
  // still swipe/arrow-click back to every earlier step of this exercise
  // (see CLAUDE.md's "Web frontend" section for why cards are separate and
  // swipeable rather than one card growing with appended content).
  //
  // Before adding the new card, this freezes the *previous* current card's
  // toolbar — clears it outright, not just disables it — so its controls
  // can never be triggered a second time once superseded. This isn't just
  // tidiness: check_answer() isn't idempotent, so a learner swiping back to
  // the original question and tapping a choice again would record a real
  // second mark against the same pair; a stale "Закрепить"/retry button
  // would similarly kick off a redundant recall. A frozen card still shows
  // its content in full, just with nothing left to click.
  _addCard(html) {
    const track = this._shadow.querySelector(".track");
    const previousCard = track.lastElementChild;
    const previousToolbar = previousCard?.querySelector(".toolbar");
    if (previousToolbar) previousToolbar.innerHTML = "";
    track.insertAdjacentHTML("beforeend", html);
    const newCard = track.lastElementChild;
    track.scrollTo({ left: newCard.offsetLeft, behavior: "smooth" });
    this._updateDeckNav();
  }

  // Attaches the two arrow buttons' click handlers (each scrolls .track by
  // one card width) and a scroll listener that keeps them in sync with
  // *however* the deck moved — a click, but just as much a swipe or a
  // trackpad scroll, neither of which goes through _addCard() at all.
  // Called once per _render() (a fresh deck), not per card.
  _wireDeckNav() {
    const track = this._shadow.querySelector(".track");
    const prev = this._shadow.querySelector("[data-deck-prev]");
    const next = this._shadow.querySelector("[data-deck-next]");
    prev.addEventListener("click", () =>
      track.scrollBy({ left: -track.clientWidth, behavior: "smooth" })
    );
    next.addEventListener("click", () =>
      track.scrollBy({ left: track.clientWidth, behavior: "smooth" })
    );
    track.addEventListener("scroll", () => this._updateDeckNav());
    this._updateDeckNav();
  }

  // Both arrows stay hidden outright — not just disabled — whenever the
  // deck holds only one card (track.scrollWidth <= track.clientWidth: no
  // overflow, nothing to page through at all) — a fresh, not-yet-answered
  // question, the only genuinely single-card state: the default
  // experience looks and behaves exactly as it did before the deck
  // existed for as long as that lasts. Once there's real overflow, each
  // arrow hides itself specifically at
  // its own end of the deck (nothing before the first card, nothing after
  // the last/current one) rather than just disabling — a hidden control
  // reads as "there's nothing that way" more clearly than a greyed-out one
  // would on a card this small. The ±1 slack absorbs sub-pixel scroll
  // position rounding, which would otherwise occasionally leave an arrow
  // spuriously enabled (or hidden) right at either end.
  _updateDeckNav() {
    const track = this._shadow.querySelector(".track");
    const prev = this._shadow.querySelector("[data-deck-prev]");
    const next = this._shadow.querySelector("[data-deck-next]");
    const hasOverflow = track.scrollWidth > track.clientWidth + 1;
    prev.hidden = !hasOverflow || track.scrollLeft <= 0;
    next.hidden =
      !hasOverflow || track.scrollLeft + track.clientWidth >= track.scrollWidth - 1;
  }

  // Builds a fresh deck from scratch, holding just this one card — the
  // only entry point that wipes everything (contrast _addCard(), which
  // never does). Correct wherever it's used: _loadNext()'s loading/error/
  // nothing-available states and its first successful _renderQuestion()
  // call, all of which mean a genuinely new exercise, where nothing from
  // any previous one is worth keeping around to swipe back to.
  _render(cardHtml) {
    this._shadow.innerHTML =
      `<style>${STYLES}</style>` +
      `<div class="deck"><div class="track">${cardHtml}</div>` +
      `<button class="deck-nav prev" data-deck-prev hidden aria-label="Previous">‹</button>` +
      `<button class="deck-nav next" data-deck-next hidden aria-label="Next">›</button></div>`;
    this._wireDeckNav();
  }
}

customElements.define("german-exercise-widget", GermanExerciseWidget);
