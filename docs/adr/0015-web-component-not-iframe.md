# 0015. The web widget is a web component, not an iframe

**Status:** Accepted, 2026-08-23 ([#176](https://github.com/pauk-slon/immer-wiederholen/pull/176))

## Context

The widget is embedded on landing pages served from another site. Its styles must not be affected by the page, and the page's styles must not be affected by it.

## Decision

`<german-exercise-widget>` is a plain-JavaScript web component rendering into a shadow root, with no build step and no dependencies, loaded from the web app.

## Alternatives considered

- **An iframe.** The same style isolation, but with a fixed size and `postMessage` messages to resize it to its content ([#176](https://github.com/pauk-slon/immer-wiederholen/pull/176)).

## Consequences

- The page can size and theme the widget through CSS custom properties, which pass into the shadow root.
- The widget runs on the page's origin, so its requests to the API are cross-origin: they need CORS (`WEB_ALLOWED_ORIGINS`) and a cookie domain shared with the page.
- Telegram's login button, a script that inserts an iframe, couldn't simply be placed in the shadow root: the widget runs the script in the page and moves the iframe into its shadow root ([#210](https://github.com/pauk-slon/immer-wiederholen/pull/210)).
