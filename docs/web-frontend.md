# Web frontend

`wiederholen.web` is the second frontend to `wiederholen.school`, next to the Telegram bot: a [Litestar](https://litestar.dev/) app with a small JSON API and two pages built on one web component. It runs as its own process (`python -m wiederholen.web`, port 8000; see [Configuration](configuration.md)).

- **The widget**, `<german-exercise-widget>`, is embedded on landing pages: a page about a grammar topic embeds a widget limited to that topic.
- **The standalone app** at `/` is the same widget as a full page, drawing from the whole course.

Learners who log in with Telegram share their progress with the bot (see [Telegram login](#telegram-login)). Some bot features aren't on the web yet: AI-generated questions, illustrations and hints from grammar classes.

## API

All exercise endpoints take a JSON body and identify the learner by the session cookie (see [Sessions](#sessions)). `language` is `ru` (default) or `en`.

| Endpoint | Body | Returns |
|---|---|---|
| `POST /api/exercise/next` | `topics`, `language` | the next exercise, or `null` if nothing is left today |
| `POST /api/exercise/check` | `answer`, `topics`, `language` | `correct`, `answer`, `explanation`, `recall` (`none`, `optional`, `required`) |
| `POST /api/exercise/recall` | `topics`, `language` | a recall: `question`, `hint` |
| `POST /api/exercise/recall/check` | `answer`, `topics` | `correct`, `answer` |
| `POST /api/client-error` | `step`, `status` | nothing (204) — see [Error reports](#error-reports) |
| `GET /api/auth/telegram/callback` | Telegram's query parameters | a redirect — see [Telegram login](#telegram-login) |

The endpoints map onto `Tutor` one to one: `next_exercise()`, `check_answer()`, `request_recall()`, `check_recall()`. They behave like the bot, side effects included — requesting an optional recall shortens the pair's next interval, a repeated recall avoids the previous one (see [Repetition schedule](repetition-schedule.md)).

**`topics`** limits the exercise to those topics, through `Course.restricted_to()`. It's applied per request and stored nowhere, so one learner's progress spans every page they've practiced on. An empty list means the whole course — that's how the standalone app works without naming every topic. The other three exercise endpoints don't restrict anything by `topics`; they use it only to find the right session (see below).

**The exercise** (`ExerciseDTO`) never includes the answer:

- `choices` — the distractors and the answer, shuffled, for a multiple-choice exercise; `null` for a typed one;
- `word_bank` — the chunks, freshly shuffled, for a word-order exercise; `null` otherwise. The widget joins the arranged chunks with spaces and sends them as a normal answer, so checking needs nothing special;
- `question`, `description`, `instruction` in the requested language.

A recall's answer isn't sent either; `/recall/check` returns the expected sentence so a wrong attempt can show it.

**409** means the learner is answering something the server no longer has in the session: `/check` or `/recall` without a shown exercise, `/recall/check` without a requested recall — usually because the session expired.

## Sessions

### The session cookie

The learner is identified by one cookie, `wiederholen_student_id`: a year long, `Secure`, `HttpOnly`, `SameSite=Lax`, on the domain in `WEB_COOKIE_DOMAIN`. A first-time visitor gets an anonymous id, `web:<random token>` (`WebStudentID`), set by the server on its first response. The server chooses it, unguessably, so a visitor can't address someone else's record by picking a value. After a Telegram login, the cookie holds a login token instead (see [The cookie](#the-cookie) under Telegram login).

`WEB_COOKIE_DOMAIN` is meant to be the parent domain of both the landing pages and the API — `example.com` for `www.example.com` and `app.example.com`. Requests between subdomains count as same-site, so `SameSite=Lax` is enough for the widget's requests to carry the cookie, without `SameSite=None` and the third-party-cookie restrictions it brings. The widget sends every request with `credentials: "include"`, and `WEB_ALLOWED_ORIGINS` lists the pages allowed to make such requests (CORS).

### What's shown: WebSessionStore

[`WebSessionStore`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/web/session.py) remembers the exercise shown to a learner and, once requested, its recall — the web equivalent of the bot's `shown_exercise` and `shown_recall` (see [Storage and identity](storage.md#chat-state)). `/check` needs it because the exercise sent to the browser has no answer to check against.

It's one JSON value per **learner and set of topics**, `web_session:{student_id}:{topics sorted and joined}`, expiring after an hour. Showing a new exercise replaces the value, dropping any recall from the previous one.

The topics are part of the key because the cookie is shared by every page on the domain. With one slot per learner, opening a second landing page between loading a question on the first and answering it would replace the shown exercise — and a correct answer on the first page would be checked against the second page's exercise and marked wrong. This happened, and `test_check_answer_is_scoped_to_its_own_topics` reproduces it. That's why every endpoint sends `topics`, even those that don't use it to pick an exercise. Two pages with the same topics share a slot, which is harmless. The language isn't part of the key: it only changes which translation of the same exercise is returned.

## The widget

[`static/widget.js`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/web/static/widget.js) is a plain-JavaScript web component — no build step, no dependencies — served at `/widget/widget.js`.

### Embedding

```html
<script src="https://app.example.com/widget/widget.js"></script>
<german-exercise-widget topics="partizip_ii,praeteritum" lang="ru"></german-exercise-widget>
```

| Attribute | Meaning |
|---|---|
| `topics` | comma-separated topics to practice; empty or missing means all |
| `lang` | `ru` (default) or `en` — for both the exercise and the widget's own texts |
| `api-base` | where the API is; defaults to the origin `widget.js` was loaded from |
| `recall` | turn on recalls (off by default) |
| `login`, `telegram-bot` | show the Telegram login button for that bot, see [The button](#the-button) |

The widget renders into a shadow root, so the page's CSS can't affect it and its CSS can't leak out. That's the reason for a web component rather than an iframe: the same isolation, without fixed sizes and `postMessage` resizing.

`api-base` defaults to the script's own origin, read from `document.currentScript` once when the script runs — it isn't available later, when the element connects.

The page can adjust the widget through CSS custom properties, which pass into the shadow root:

| Property | Default | Meaning |
|---|---|---|
| `--gew-max-width` | `28rem` | the widget's maximum width |
| `--gew-height` | `16rem` | the fixed height of every card |
| `--gew-fg`, `--gew-muted`, `--gew-bg`, `--gew-border`, `--gew-choice-bg`, `--gew-primary`, `--gew-correct`, `--gew-wrong` | light and dark palettes | colors |

### Texts and colors

The exercise comes from the API in the requested language; the widget's own texts — buttons, "Correct!", error messages — are in `STRINGS` in `widget.js`, falling back to Russian like `lang` itself.

The widget defines all its colors itself and switches them for `prefers-color-scheme: dark`; it can't read the host page's theme through the shadow boundary. Cards, buttons and inputs get an explicit background, and controls `color: inherit`: with transparent backgrounds, dark text ended up on a dark page's dark background.

### A deck of cards

Each step of an exercise is a separate card — the question, the result, a recall, a recall's result — in a horizontally scrolling row (`.track` inside `.deck`). CSS scroll snapping lands every swipe on a card; two arrow buttons page between cards and hide at the ends, or entirely when there's only one card.

This replaced recall steps appended into one card, which read like a chat transcript in a box. With cards, the explanation is still one swipe away while the learner works on a recall — what the bot's scrolling chat gives for free.

How the deck changes:

- **A new exercise** starts a fresh deck with one card (`_render()`).
- **The result** also starts a fresh deck: the question is replaced by the result, which already shows the answer, and keeping the question card would leave dead controls to swipe back to.
- **A recall** adds a card after the result (`_addCard()`). Each new recall attempt or recall result replaces the previous recall card instead of piling up: only the explanation and the current recall step stay.

When a card is added, the previous card's buttons are removed. This isn't tidiness: `check_answer()` isn't idempotent, so tapping an old card's option again would record a second answer for the same pair.

### Answering and recalls

After an answer, the result card shows the verdict, the explanation and, depending on `recall` (always `none` without the `recall` attribute):

- **`none`**: "Next";
- **`optional`** (right answer): "Drill" and "Next";
- **`required`** (wrong answer): "Drill" only. It's a button rather than starting the recall right away, so the learner has time to read the explanation the recall builds on.

A recall card says what to do ("Reconstruct the phrase"), shows the recall question and hint, and takes a typed answer. A wrong attempt offers "Try again" — which fetches a recall again, usually a different one — and "Next".

The widget doesn't underline the differences in a wrong recall the way the bot does; it shows the expected sentence.

If a request fails, the current card shows an error and "Next" instead of its buttons; nothing already shown is wiped. A failed answer isn't retried with the same request: the usual cause is a 409 from an expired session, which would fail again. Loading a new exercise recovers.

### Layout

Every card has the same fixed height, `--gew-height`, so answering or paging never resizes the widget and shifts the page around it. The default leaves room for a long sentence wrapped on a phone.

Inside a card:

- **`.body`** holds the content and scrolls on its own if it's too long; the buttons (`.toolbar`) stay below it, always visible. A short fade at the bottom of `.body` hints that there's more to scroll.
- **`.centered-pair`** groups the two pieces of text that belong together and centers them as one: the question and its description, the verdict and its explanation, a recall question and its hint. The instruction, when there is one, sits above it.
- **Options** are a two-column grid, so buttons in a row have equal widths and columns line up — almost every exercise has four options.
- **Buttons** are in a two-column `.actions` grid too; a single button spans both columns. The last button is the primary, blue one.
- **Loading, error and "nothing left" messages** are centered on their card.
- **Word-order exercises** have their own layout: the question, the description, then the shuffled chunks as tiles. Tapping a tile moves it to the answer row; tapping it there moves it back. When no tiles are left, the answer is submitted — there's no submit button — and the tiles are disabled so it can't be sent twice.

### Reloading the page

The shown exercise is cached in `sessionStorage`, keyed by topics and language, and a reload shows it again instead of fetching a new one — the server's session hasn't moved on either. The cache is cleared as soon as an answer's result arrives, so a reload on the result screen can't bring the answered question back. `sessionStorage` rather than `localStorage`: it survives reloads but not the end of the visit, which roughly matches the server's one-hour session. If they still drift apart, the answer gets a 409 and the learner sees the error and "Next".

### Focus and the mobile keyboard

The typed-answer field and the "Next" button get focus when they appear, so Enter works without clicking — keyboard events wouldn't reach the shadow root while focus is on `<body>`. Focusing uses `preventScroll`, so a widget lower down a page doesn't pull the page to itself.

On a fresh page load the input isn't focused: on a phone, that would open the keyboard before the learner did anything. Only after a tap ("Next", "Try again", "Drill") does it get focus.

When the keyboard opens for the answer field, the browser scrolls just the field into view, leaving the question behind the keyboard. The widget listens to `visualViewport` resizes and, while its input is focused, scrolls the whole widget to the middle of the screen.

### Error reports

When a request fails, the widget posts the step (`_loadNext`, `_submitAnswer`, `_startRecall` or `_submitRecallAnswer`) and the HTTP status, if there was a response, to `POST /api/client-error`. The server logs a warning and records them as attributes of that request's span (see [Tracing](tracing.md#what-gets-traced)), so browser-side failures show up next to the server's traces instead of in a separate tool. Reporting is fire-and-forget: a failed report never causes an error of its own.

This exists because a real failure — a 409 on `/check` — once showed up only as an access-log line and took a manual browser reproduction to understand.

## The standalone app

[`static/app/`](https://github.com/pauk-slon/immer-wiederholen/tree/main/wiederholen/web/static/app) is served at `/`. It's the same `<german-exercise-widget>`, as the page's main content and without `topics`, so it practices the whole course. It turns on `recall` and the Telegram login — the app is meant to grow toward what the bot offers, while an embedded widget stays a light sample.

It loads `widget.js` from `/widget/widget.js` on the same origin. The page sets `--gew-max-width: 36rem` and `--gew-height: 26rem` for a bigger card, since practicing is the page's whole purpose.

Its only control is a language switch (`app.js`), saved in `localStorage` as `wiederholen-lang`. An inline script before `widget.js` applies the saved language to the widget's `lang`, and switching reloads the page — the widget doesn't react to `lang` changing after it's connected. The page's own texts are Russian only. It has no promotional content of its own: that belongs to the content repo, not the app shell.

## Telegram login

A learner who practices with the Telegram bot can log in to the web app with the same Telegram account and continue with the same progress. It uses the [Telegram Login Widget](https://core.telegram.org/widgets/login), Telegram's own redirect-based scheme — not OAuth or OpenID Connect, which Telegram doesn't offer.

### How it works

1. The widget shows Telegram's login button (see [The button](#the-button)). After the learner confirms in Telegram, the browser is redirected to `GET /api/auth/telegram/callback` with the learner's Telegram id, name, `username` and `photo_url` if they have them, `auth_date`, and a `hash` signing all of these.
2. [`validate_telegram_login()`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/web/telegram_login.py) checks the signature: `hash` must equal HMAC-SHA256 of the other fields — sorted, joined as `key=value` lines — keyed with SHA-256 of `BOT_TOKEN`. It also rejects an `auth_date` older than a day, so an old callback URL from browser history can't be replayed. Any failure — bad signature, too old, missing or malformed `id` or `auth_date` — is a 400.
3. The Telegram id is resolved with `StudentIdentityStore.resolve_or_create_student_id("telegram", ...)` — exactly what the bot does for a chat, so both reach the same learner (see [Storage and identity](storage.md#student-identity)).
4. The callback creates a new **browser token** (`secrets.token_urlsafe(32)`), links it to that learner as a `"browser"` login, stores `browser:<token>` in the session cookie, and redirects back.

This is the only reason the web app needs `BOT_TOKEN`: to check signatures, not to call the Bot API.

### The cookie

The web app has one cookie, `wiederholen_student_id` (a year, `Secure`, `HttpOnly`, `SameSite=Lax`, on `WEB_COOKIE_DOMAIN`). It holds one of two things:

- **`browser:<token>`** after a Telegram login. The token is resolved with `StudentIdentityStore.resolve_student_id("browser", token)`. If it doesn't resolve — the store was wiped, or the value was tampered with — the visitor is treated as new and anonymous, never as a newly created learner.
- **an anonymous id**, `web:<random token>`, minted on a visitor's first request (`WebStudentID`). Anything that is neither is ignored, and the visitor gets a fresh anonymous id.

The cookie never holds the `StudentID` itself, only a login that resolves to it. A leaked cookie doesn't reveal the learner's permanent id. There's no logout yet — only clearing the cookie — but adding one would only mean deleting that one `browser` login.

Each login creates a new token instead of reusing the one the browser already has: on a shared browser, the old token may belong to a different learner, and `link_identity()` refuses to move a login from one learner to another.

**Progress made anonymously isn't carried over.** After logging in, the browser continues as the Telegram learner; what it practiced before logging in stays with the abandoned anonymous id.

### Redirecting back

The widget adds `return_to` — the page the button was clicked on — to the callback URL. It isn't one of Telegram's signed fields, so it's removed before the signature check. `_safe_redirect_target()` follows it only if it is:

- a path on the same site (`/...`, but not `//host/...`, which browsers treat as another site), or
- an absolute URL whose origin is in `WEB_ALLOWED_ORIGINS`.

Anything else redirects to `/`, so the callback can't be used to send visitors to an arbitrary site.

### The button

`<german-exercise-widget>` shows the button when it has a bare `login` attribute and `telegram-bot="BotUsername"` naming the bot; it's off by default. The standalone app (`static/app/index.html`) turns it on for `ImmerWiederholenBot`. An embedding page can too, but only on the domain registered for the bot with BotFather's `/setdomain` — Telegram allows one domain per bot.

Telegram's button is a script that inserts an iframe, and a `<script>` added via `innerHTML` never runs. So the widget creates the script element in the page's light DOM, waits for Telegram to insert the iframe (`MutationObserver`), and moves the iframe into its shadow root — moving an iframe doesn't reload it. The button is rendered once per connection, in its own container, and later re-renders of the exercise card don't touch it, so it doesn't flicker or reload on every answer.

The widget doesn't know whether the browser is logged in: the button keeps showing, and nothing on the page says who's logged in. Clicking it again is harmless — it resolves the same learner.

### Testing the login

`telegram_login_payload_factory` in [`tests/plugins/telegram_login.py`](https://github.com/pauk-slon/immer-wiederholen/blob/main/tests/plugins/telegram_login.py) builds a callback payload signed with the test bot token, so tests can call the callback with a valid login and then tamper with single fields.

## Testing

Web tests use `litestar.testing.AsyncTestClient`, not the synchronous `TestClient`. The synchronous client serves the app from its own thread and event loop, and a Redis connection opened on the test's loop can't be used from another one (`RuntimeError: ... attached to a different loop`).

For the same reason, `web_app_factory` in `tests/web/test_app.py` builds fresh store objects for the app rather than reusing the test's own: it depends on the store fixtures only so their databases are flushed, and the app's first Redis call then happens on the loop that serves it.

The client needs `base_url="https://..."`. The session cookie is `Secure`, and httpx — like a browser — doesn't send a `Secure` cookie over plain HTTP, so with the default `http://` every cookie would silently disappear between requests.

Requests are traced by Litestar's `OpenTelemetryPlugin` (see [Tracing](tracing.md)).

## Design notes

- **A web component, not an iframe.** The shadow root isolates styles in both directions without an iframe's fixed size and resize messaging.
- **One component for both pages.** The embed and the app differ only in attributes (`recall`, `login`) and two size properties, so every fix applies to both; a forked app version would need each fix twice.
- **Recalls are opt-in.** An embedded widget is a quick taste of practicing; the full bot-like flow is for the app.
- **The server picks the anonymous id.** A client-chosen id could be set to someone else's.
- **Client errors go into the existing traces**, not a separate error tracker: one place to look for a problem that spans the browser and the server.
- **Lessons from real reports**, kept so they aren't undone:
  - a required recall waits for a tap — starting it right away flashed the explanation past before it could be read;
  - the question card is dropped once answered — swiping back showed dead controls;
  - every card has a fixed height — a growing card pushed the page around on every step;
  - the fade at the bottom of `.body` is a fixed `0.35rem` — a percentage made whole lines look faded on the app's taller card;
  - options are a fixed two-column grid — `auto-fit` sometimes made three columns and left the fourth option alone on a row;
  - `.deck-nav[hidden] { display: none; }` is explicit — the arrows' own `display: flex` otherwise overrides the `hidden` attribute.
