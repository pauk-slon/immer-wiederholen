# 0015. The web widget is a web component, not an iframe

**Status:** Accepted, 2026-08-23 ([#176](https://github.com/pauk-slon/immer-wiederholen/pull/176))

## Context

The widget is embedded on landing pages from another site. The styles of the page must not affect the widget, and the styles of the widget must not affect the page.

## Decision

`<german-exercise-widget>` is a web component in plain JavaScript that renders into a shadow root. It has no build step and no dependencies, and the web app serves it.

## Alternatives considered

- **An iframe.** It gives the same style isolation. But it has a fixed size and needs `postMessage` messages to resize it to its content ([#176](https://github.com/pauk-slon/immer-wiederholen/pull/176)).

## Consequences

- The page can set the size and the theme of the widget through CSS custom properties, which pass into the shadow root.
- The widget runs on the origin of the page, so its requests to the API are cross-origin. They need CORS (`WEB_ALLOWED_ORIGINS`) and a cookie domain that the page shares.
- Telegram's login button is a script that inserts an iframe. The widget couldn't simply put it into the shadow root. Instead, the widget runs the script in the page and moves the iframe into its shadow root ([#210](https://github.com/pauk-slon/immer-wiederholen/pull/210)).
