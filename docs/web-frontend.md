# Web frontend

`wiederholen.web` is the second frontend to `wiederholen.school`, next to the Telegram bot. It is a [Litestar](https://litestar.dev/) app with a small JSON API and two pages that use one web component. It runs as its own process (`python -m wiederholen.web`, port 8000, see [Configuration](configuration.md)).

- **The widget**, `<german-exercise-widget>`, is embedded on landing pages. A page about a grammar topic embeds a widget that is limited to that topic.
- **The standalone app** at `/` is the same widget as a full page. It uses the whole course.

Learners who log in with Telegram share their progress with the bot (see [Telegram login](#telegram-login)). Some features of the bot aren't on the web yet. These are topic selection, reminders, AI-generated exercises, illustrations and hints from grammar classes.

## API

All exercise endpoints take a JSON body and identify the learner by the session cookie (see [Sessions](#sessions)). `language` is `ru` (the default) or `en`.

| Endpoint | Body | Returns |
|---|---|---|
| `POST /api/exercise/next` | `topics`, `language` | the next exercise, or `null` if nothing is left today |
| `POST /api/exercise/check` | `answer`, `topics`, `language` | `correct`, `answer` (the correct answers that the topic shows, separated by ` / `), `explanation`, `recall` (`none`, `optional`, `required`) |
| `POST /api/exercise/recall` | `topics`, `language` | a recall with `question` and `hint` |
| `POST /api/exercise/recall/check` | `answer`, `topics`, but no `language`, because the expected sentence is German | `correct`, `answer` |
| `POST /api/client-error` | `step`, `status` | nothing (204, see [Error reports](#error-reports)) |
| `GET /api/auth/telegram/callback` | Telegram's query parameters | a redirect (see [Telegram login](#telegram-login)) |

For example:

```http
POST /api/exercise/next
Content-Type: application/json

{"topics": ["verb_preposition"], "language": "en"}
```

```json
{
  "word": "warten",
  "topic": "verb_preposition",
  "question": "Wir warten schon zehn Minuten ___ den Zug.",
  "choices": ["an", "auf", "um", "für"],
  "description": null,
  "instruction": null,
  "word_bank": null
}
```

Each exercise endpoint calls one method of `Tutor`. These are `next_exercise()`, `check_answer()`, `request_recall()` and `check_recall()`. The endpoints behave like the bot, with the same side effects. For example, a request for an optional recall shortens the next interval of the pair, and a repeated recall avoids the previous one (see [Repetition schedule](repetition-schedule.md)).

**`topics`** limits the exercise to those topics through `Course.restricted_to()`. The limit applies to one request, and the server doesn't store it, so the progress of a learner includes every page where they practiced. An empty list means the whole course. This is how the standalone app works without a list of all topics. The other three exercise endpoints don't restrict anything by `topics`. They use it only to find the right session (see below).

**The exercise** (`ExerciseDTO`) never includes the answer:

- `choices` has the distractors and the answers that the topic shows, shuffled, for a multiple-choice exercise (see [Several correct answers](course-format.md#several-correct-answers)). It is `null` for a typed exercise.
- `word_bank` has the chunks, shuffled again for each request, for a word-order exercise. It is `null` otherwise. The widget joins the arranged chunks with spaces and sends them as a normal answer, so the check needs no special case.
- `question`, `description` and `instruction` are in the requested language.

The server doesn't send a recall's answer either. `/recall/check` returns the expected sentence, so the widget can show it after a wrong attempt.

**409** means that the learner answers something that the session no longer has. Examples are `/check` or `/recall` without a shown exercise, and `/recall/check` without a requested recall. The usual cause is an expired session.

## Sessions

### The session cookie

One cookie identifies the learner, `wiederholen_student_id`. It is valid for a year and is `Secure`, `HttpOnly` and `SameSite=Lax`, on the domain in `WEB_COOKIE_DOMAIN`. A first-time visitor gets an anonymous id, `web:<random token>` (`WebStudentID`), which the server sets on its first response. The server generates a random id, so a visitor can't pick a value that addresses another learner's record. After a Telegram login, the cookie holds a login token instead (see [The cookie](#the-cookie) under Telegram login).

Set `WEB_COOKIE_DOMAIN` to the parent domain of both the landing pages and the API, such as `example.com` for `www.example.com` and `app.example.com`. Requests between subdomains count as same-site, so with `SameSite=Lax` the requests of the widget carry the cookie. This avoids `SameSite=None` and its restrictions on third-party cookies. The widget sends every request with `credentials: "include"`, and `WEB_ALLOWED_ORIGINS` lists the pages that can make such requests (CORS).

### What's shown: WebSessionStore

[`WebSessionStore`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/web/session.py) stores the exercise shown to a learner and, after a request, its recall. It does on the web what `shown_exercise` and `shown_recall` do in the bot (see [Storage and identity](storage.md#chat-state)). `/check` needs it, because the exercise sent to the browser has no answer to check against.

The store has one JSON value per **learner and set of topics**, under `web_session:{student_id}:{topics sorted and joined}`. The value expires after an hour. A new exercise replaces the value and removes any recall of the previous exercise.

The topics are part of the key, because all pages on the domain share the cookie. Suppose there was one value per learner. A learner loads a question on one landing page, opens a second landing page and then answers on the first. The second page would replace the shown exercise. Then the server would check a correct answer on the first page against the exercise of the second page and mark it wrong. `test_check_answer_is_scoped_to_its_own_topics` reproduces this case. For this reason, every endpoint sends `topics`, even the endpoints that don't use it to pick an exercise. Two pages with the same topics share a value, and this does no harm. The language isn't part of the key, because it only changes which translation of the same exercise the server returns (see [ADR 0016](adr/0016-web-sessions-keyed-by-topics.md)).

## Embedding the widget

[`static/widget.js`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/web/static/widget.js) is a web component in plain JavaScript, with no build step and no dependencies. The web app serves it at `/widget/widget.js`.

```html
<script src="https://app.example.com/widget/widget.js"></script>
<german-exercise-widget topics="partizip_ii,praeteritum" lang="ru"></german-exercise-widget>
```

| Attribute | Meaning |
|---|---|
| `topics` | comma-separated topics to practice. Empty or missing means all topics |
| `lang` | `ru` (the default) or `en`, for both the exercise and the widget's own texts |
| `api-base` | the location of the API. The default is the origin that `widget.js` was loaded from |
| `recall` | enables recalls (off by default) |
| `login`, `telegram-bot` | show the Telegram login button for that bot (see [The button](#the-button)) |

The widget renders into a shadow root, so the CSS of the page can't affect the widget, and the CSS of the widget can't affect the page. This is the reason for a web component and not an iframe. It gives the same isolation without fixed sizes and without resizing through `postMessage` (see [ADR 0015](adr/0015-web-component-not-iframe.md)).

The default of `api-base` is the script's own origin. The widget reads it from `document.currentScript` once, when the script runs, because `document.currentScript` isn't available later, when the element connects.

The real embeds are the landing pages in the content repo (`immer-wiederholen-de`), on GitHub Pages. They load the widget through a small `widget-loader.js` that chooses the local or the production API, because the pages themselves don't know their environment. The standalone app needs no loader, because the web app serves it.

The page can change the widget through CSS custom properties, which pass into the shadow root:

| Property | Default | Meaning |
|---|---|---|
| `--gew-max-width` | `28rem` | the widget's maximum width |
| `--gew-height` | `16rem` | the fixed height of every card |
| `--gew-fg`, `--gew-muted`, `--gew-bg`, `--gew-border`, `--gew-choice-bg`, `--gew-primary`, `--gew-correct`, `--gew-wrong` | light and dark palettes | colors |

## How the widget works

### Texts and colors

The API returns the exercise in the requested language. The widget's own texts, such as buttons, "Correct!" and error messages, are in `STRINGS` in `widget.js`. If the language is unknown, they use Russian, as `lang` does.

The widget defines all its colors and changes them for `prefers-color-scheme: dark`. It can't read the theme of the host page through the shadow boundary. Cards, buttons and inputs get an explicit background, and controls get `color: inherit`. Without them, dark text would appear on the dark background of a dark page.

### A deck of cards

Each step of an exercise is a separate card. The steps are the question, the result, a recall and a recall's result. The cards are in a row that scrolls horizontally (`.track` inside `.deck`). CSS scroll snapping stops every swipe on a card. Two arrow buttons move between the cards. They hide at the ends, and they hide completely when there is only one card. To hide the arrows, the widget needs an explicit `.deck-nav[hidden] { display: none; }`, because their own `display: flex` overrides the `hidden` attribute.

Cards keep the explanation one swipe away while the learner works on a recall. The bot's chat gives this automatically, because the learner can scroll back. A single card with all recall steps would read like a chat transcript in a box.

The deck changes in these ways:

- **A new exercise** starts a new deck with one card (`_render()`).
- **The result** also starts a new deck. The result replaces the question, because the result already shows the answer, and a question card would leave controls that no longer work.
- **A recall** adds a card after the result (`_addCard()`). Each new recall attempt or recall result replaces the previous recall card, so the cards don't accumulate. Only the explanation and the current recall step stay.

When the widget adds a card, it removes the buttons of the previous card. This is necessary, because `check_answer()` isn't idempotent. Another tap on an option of an old card would record a second answer for the same pair.

### Answering and recalls

After an answer, the result card shows the verdict and the explanation. Its buttons depend on `recall`, which is always `none` without the `recall` attribute:

- **`none`.** The card shows "Next".
- **`optional`** (right answer). The card shows "Drill" and "Next".
- **`required`** (wrong answer). The card shows only "Drill". The recall starts with a button, not at once, so the learner has time to read the explanation that the recall builds on.

A recall card tells the learner what to do ("Reconstruct the phrase"). It shows the recall question and the hint and takes a typed answer. After a wrong attempt, it shows "Try again" and "Next". "Try again" gets a recall again, usually a different one.

The widget doesn't underline the differences in a wrong recall like the bot. It shows the expected sentence.

If a new exercise fails to load, the widget shows an error card with "Try again". If a request inside an exercise fails, such as an answer or a recall, the current card shows an error and "Next" in place of its buttons. The widget doesn't remove what it already showed. It doesn't send a failed answer again with the same request. The usual cause is a 409 from an expired session, and the same request would fail again. The learner continues with a new exercise.

### Layout

Every card has the same fixed height, `--gew-height`, so the widget never changes size when the learner answers or moves between cards, and the page around it doesn't move. The default of 16rem leaves room for a long sentence on a phone. A height of 14rem cuts such a sentence.

A card has these parts:

- **The content area** (`.body`) scrolls by itself if it's too long. The buttons below it (`.toolbar`) stay visible. A short fade at the bottom shows that there is more content. The fade is a fixed `0.35rem`, because a fade as a percentage of the height made whole lines look faded on the taller card of the app.
- **Two pieces of text that belong together** (`.centered-pair`) are centered as one group. Examples are the question and its description, the verdict and its explanation, and a recall question and its hint. The instruction, if there is one, is above the group.
- **Options** are in a grid with two columns, so the buttons in a row have equal widths and the columns align. Almost every exercise has four options. The grid has a fixed two columns and doesn't use `auto-fit`, because `auto-fit` sometimes made three columns and left the fourth option alone in a row.
- **Buttons** are also in a grid with two columns (`.actions`). A single button spans both columns. The last button is the primary, blue one.
- **Loading, error and "nothing left" messages** are centered on their card.
- **Word-order exercises** have their own layout. It shows the question, the description and then the shuffled chunks as tiles. A tap on a tile moves it to the answer row, and a tap there moves it back. When no tiles are left, the widget submits the answer, because there is no submit button. It then disables the tiles, so the answer can't be sent twice.

### Reloading the page

The widget stores the shown exercise in `sessionStorage`, with topics and language as the key. A reload shows this exercise again and doesn't load a new one, because the server's session also still has it. The widget clears the stored exercise when the result of an answer arrives, so a reload on the result screen can't show the answered question again. The widget uses `sessionStorage` and not `localStorage`, because `sessionStorage` keeps its data after a reload but not after the visit ends. This is close to the server's session of one hour. If the two still differ, the answer gets a 409, and the learner sees the error and "Next".

### Focus and the mobile keyboard

The field for a typed answer and the "Next" button get focus when they appear, so Enter works without a click, because keyboard events don't reach the shadow root while `<body>` has focus. The focus uses `preventScroll`, so a widget lower on a page doesn't scroll the page to itself.

When the page first loads, the input doesn't get focus. On a phone, focus would open the keyboard before the learner did anything. The input gets focus only after a tap ("Next", "Try again", "Drill").

When the keyboard opens for the answer field, the browser scrolls only the field into view, and the question stays behind the keyboard. The widget listens for `visualViewport` resizes. While its input has focus, it scrolls the whole widget to the middle of the screen.

### Error reports

When a request fails, the widget posts the step (`_loadNext`, `_submitAnswer`, `_startRecall` or `_submitRecallAnswer`) and the HTTP status, if there was a response, to `POST /api/client-error`. The server logs a warning and records the values as attributes of the span of that request (see [Observability](tracing.md#what-gets-traced)), so browser-side failures appear next to the server's traces and not in a separate tool. The widget doesn't wait for the report, and a failed report never causes an error of its own.

Without these reports, a failure in the browser appears only as a line in the access log, and only a manual reproduction in a browser explains it. The reports go into the existing traces and not into a separate error tracker, so there is one place to look for a problem that involves both the browser and the server.

## The standalone app

The web app serves [`static/app/`](https://github.com/pauk-slon/immer-wiederholen/tree/main/wiederholen/web/static/app) at `/`. The app is the same `<german-exercise-widget>`, as the main content of the page and without `topics`, so it uses the whole course. It enables `recall` and the Telegram login. The app is meant to grow toward the features of the bot, and an embedded widget stays a light sample. Both pages use one component and differ only in attributes and two size properties, so every fix applies to both.

The app loads `widget.js` from `/widget/widget.js` on the same origin. The page sets `--gew-max-width: 36rem` and `--gew-height: 26rem` for a bigger card, because practice is the only purpose of the page.

Its only control is a language switch (`app.js`). The switch saves the language in `localStorage` as `wiederholen-lang`. An inline script before `widget.js` sets the widget's `lang` to the saved language. A switch reloads the page, because the widget doesn't react to a change of `lang` after it connects. The page's own texts are only in Russian. The page has no promotional content, because such content belongs in the content repo and not in the app.

## Telegram login

A learner who practices with the Telegram bot can log in to the web app with the same Telegram account and continue with the same progress. The login uses the [Telegram Login Widget](https://core.telegram.org/widgets/login). This is Telegram's own scheme with redirects. It isn't OAuth or OpenID Connect, because Telegram doesn't offer them.

### How it works

1. The widget shows Telegram's login button (see [The button](#the-button)). After the learner confirms in Telegram, the browser goes to `GET /api/auth/telegram/callback`. The request has the learner's Telegram id, name, `username` and `photo_url` if they have them, `auth_date`, and a `hash` that signs all of these.
2. [`validate_telegram_login()`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/web/telegram_login.py) checks the signature. `hash` must equal the HMAC-SHA256 of the other fields, sorted and joined as `key=value` lines, with the SHA-256 of `BOT_TOKEN` as the key. The function also rejects an `auth_date` older than a day, so nobody can replay an old callback URL from the browser history. The callback returns a 400 for every failure, such as a bad signature, a login that is too old, or a missing or malformed `id` or `auth_date`.
3. `StudentIdentityStore.resolve_or_create_student_id("telegram", ...)` resolves the Telegram id. The bot does exactly the same for a chat, so both frontends get the same learner (see [Storage and identity](storage.md#student-identity)).
4. The callback creates a new **browser token** (`secrets.token_urlsafe(32)`) and links it to that learner as a `"browser"` login. It stores `browser:<token>` in the session cookie and redirects back.

This is the only reason why the web app needs `BOT_TOKEN`. The web app uses the token to check signatures, not to call the Bot API.

### The cookie

The session cookie (see [The session cookie](#the-session-cookie)) holds one of two values:

- **`browser:<token>`** after a Telegram login. `StudentIdentityStore.resolve_student_id("browser", token)` resolves the token. The token doesn't resolve if the store was deleted or someone changed the value. Then the visitor gets a new anonymous id. The server never creates a learner for such a token.
- **An anonymous id**, `web:<random token>`, in all other cases. The server ignores a value of any other form, and the visitor gets a new anonymous id.

The cookie never holds the `StudentID` itself, only a login that resolves to it, so a leaked cookie doesn't show the learner's permanent id. There's no logout yet. To log out, clear the cookie. A logout would only need to delete that one `browser` login.

Each login creates a new token and doesn't reuse the token that the browser already has. On a shared browser, the old token can belong to a different learner, and `link_identity()` refuses to move a login from one learner to another.

**Anonymous progress isn't moved to the Telegram learner.** After the login, the browser continues as the Telegram learner. What the browser practiced before the login stays with the old anonymous id.

### Redirecting back

The widget adds `return_to` to the callback URL. `return_to` is the page where the learner clicked the button. It isn't one of Telegram's signed fields, so the callback removes it before the signature check. `_safe_redirect_target()` follows it only in two cases:

- a path on the same site (`/...`, but not `//host/...`, because browsers treat that as another site)
- an absolute URL with an origin in `WEB_ALLOWED_ORIGINS`

For any other value, the callback redirects to `/`, so nobody can use the callback to send visitors to an arbitrary site.

### The button

`<german-exercise-widget>` shows the button if it has a bare `login` attribute and `telegram-bot="BotUsername"` with the name of the bot. The button is off by default. The standalone app (`static/app/index.html`) enables it for `ImmerWiederholenBot`. An embedding page can enable it too, but only on the domain that is registered for the bot with BotFather's `/setdomain`. Telegram allows one domain per bot.

Telegram's button is a script that inserts an iframe, and a `<script>` added through `innerHTML` never runs. For this reason, the widget creates the script element in the light DOM of the page. It waits until Telegram inserts the iframe (`MutationObserver`) and moves the iframe into its shadow root. A move of an iframe doesn't reload it. The widget renders the button once per connection, in its own container. Later renders of the exercise card don't change it, so the button doesn't flicker or reload after every answer.

The widget doesn't know whether the browser is logged in. The button stays visible, and the page doesn't show who is logged in. Another click on the button does no harm, because it resolves the same learner.

### Testing the login

`telegram_login_payload_factory` in [`tests/plugins/telegram_login.py`](https://github.com/pauk-slon/immer-wiederholen/blob/main/tests/plugins/telegram_login.py) builds a callback payload signed with the test bot token. Tests can call the callback with a valid login and then change single fields.

## Running locally

`docker compose up` starts the `web` service, but `compose.yaml` doesn't publish its port. To open the app on your machine, publish the port in a gitignored `compose.override.yaml`:

```yaml
services:
  web:
    ports:
      - "8000:8000"
```

Then open `http://localhost:8000/`. To try an embed on your own page, add the origin of the page to `WEB_ALLOWED_ORIGINS`. Nobody has checked yet whether the session cookie works on plain `http://localhost` with the default settings (see [#256](https://github.com/pauk-slon/immer-wiederholen/issues/256)).

## Testing

Web tests use `litestar.testing.AsyncTestClient`, not the synchronous `TestClient`. The synchronous client serves the app from its own thread and event loop. A Redis connection opened on the loop of the test can't be used from another loop (`RuntimeError: ... attached to a different loop`).

For the same reason, `web_app_factory` in `tests/web/test_app.py` builds new store objects for the app and doesn't reuse the stores of the test. It depends on the store fixtures only so that their databases are flushed. The first Redis call of the app then happens on the loop that serves it.

The client needs `base_url="https://..."`. The session cookie is `Secure`, and httpx, like a browser, doesn't send a `Secure` cookie over plain HTTP. With the default `http://`, every cookie would silently disappear between requests.

Litestar's `OpenTelemetryPlugin` traces the requests (see [Observability](tracing.md)).

## Decisions

- [Separate learners from the ways they log in](adr/0003-separate-accounts-from-logins.md) (ADR 0003)
- [The web widget is a web component, not an iframe](adr/0015-web-component-not-iframe.md) (ADR 0015)
- [Web sessions are keyed by learner and topics](adr/0016-web-sessions-keyed-by-topics.md) (ADR 0016)
