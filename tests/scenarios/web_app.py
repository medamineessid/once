"""A real, local, headless web app for the scenario lab.

The pages are served over HTTP on 127.0.0.1 by a stdlib server and parsed with
``html.parser``; no browser is launched and no external network is used. Each
variant changes the DOM the way real sites do: adverts appear above the
results, a cookie banner appears, an element loses its ``id``, a label changes,
the list is re-rendered, or the row moves to page 2.

Every clickable element carries ``data-key``. That key is the lab's internal
handle for performing a click and for knowing which element was meant — it is
never exposed as a clue, so the resolver cannot cheat by reading it.
"""

from __future__ import annotations

import threading
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from engine.resolve import Candidate, Clue, ClueKind

HOST = "127.0.0.1"
ROW_TARGET = "Invoice 1042"
MAX_PAGES = 3
INTERACTIVE_TAGS = frozenset({"button", "a"})


def _row(invoice: str, *, dom_id: bool = True, text: str = "Edit", key: str | None = None) -> str:
    element_id = f' id="edit-{invoice.split()[-1]}"' if dom_id else ""
    data_key = key or f"edit-{invoice.split()[-1]}"
    return (
        f'<li aria-label="{invoice}" data-row="{invoice}">'
        f'<span class="cell">{invoice}</span>'
        f'<button{element_id} data-key="{data_key}">{text}</button>'
        "</li>"
    )


def _ads() -> str:
    return "".join(
        f'<aside class="ad" aria-label="Sponsored"><p>Great offer {index}</p>'
        f'<button data-key="ad-{index}">Buy now</button></aside>'
        for index in range(1, 4)
    )


def _banner() -> str:
    return (
        '<div role="alert" aria-label="Cookie notice">'
        "<p>We use cookies.</p>"
        '<button data-key="dismiss-cookies">Accept all</button>'
        "</div>"
    )


def _render_rows(variant: str, page: int, edited: str | None) -> str:
    rows: list[str] = []
    next_link = ""
    if variant in {"A", "B", "C"}:
        rows = [_row(f"Invoice {number}") for number in range(1040, 1045)]
    elif variant == "D":
        if page == 1:
            rows = [_row(f"Invoice {number}") for number in range(1050, 1053)]
            next_link = '<a href="?page=2" data-key="next-page">Next page</a>'
        else:
            rows = [_row(f"Invoice {number}") for number in range(1042, 1044)]
    prefix = ""
    if variant == "B":
        prefix = _ads()
    if variant == "C":
        prefix = _banner()
    status = f'<p id="status">Last action: {edited}</p>' if edited else ""
    return (
        "<html><body>"
        f"{prefix}"
        "<main><h1>Invoices</h1>"
        f'<ul aria-label="Invoices">{"".join(rows)}</ul>'
        f"<nav>{next_link}</nav>"
        f"{status}"
        "</main></body></html>"
    )


def _render_form(variant: str, page: int, edited: str | None) -> str:
    del page
    if variant == "A":
        body = (
            f'<section aria-label="{ROW_TARGET}"><h2>{ROW_TARGET}</h2>'
            '<button id="edit-1042" data-key="edit-1042">Edit</button></section>'
        )
    elif variant == "B":
        body = (
            f'<section aria-label="{ROW_TARGET}"><h2>{ROW_TARGET}</h2>'
            '<button data-key="edit-1042">Modify</button></section>'
        )
    elif variant == "C":
        body = (
            '<section aria-label="Invoice 1042"><h2>Invoice 1042</h2>'
            '<button data-key="edit-1042a">Edit</button></section>'
            '<section aria-label="Invoice 1042"><h2>Invoice 1042</h2>'
            '<button data-key="edit-1042b">Edit</button></section>'
        )
    else:
        body = (
            '<section aria-label="Invoice 1099"><h2>Invoice 1099</h2>'
            '<button data-key="edit-1099">Edit</button></section>'
        )
    status = f'<p id="status">Last action: {edited}</p>' if edited else ""
    return f"<html><body><main>{body}{status}</main></body></html>"


def render_page(kind: str, variant: str, page: int, edited: str | None) -> str:
    """Return the HTML for one variant page (deterministic, no state)."""
    if kind == "rows":
        return _render_rows(variant, page, edited)
    return _render_form(variant, page, edited)


class WebApp:
    """A tiny stateful HTTP app served from this test process."""

    def __init__(self, kind: str) -> None:
        self.kind = kind
        self.variant = "A"
        self.page = 1
        self.edited: str | None = None
        self._server = ThreadingHTTPServer((HOST, 0), _make_handler(self))
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}"

    def start(self) -> WebApp:
        self._thread.start()
        return self

    def reset(self, variant: str) -> None:
        """Put the app into one variant's start state."""
        self.variant = variant
        self.page = 1
        self.edited = None

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()

    def __enter__(self) -> WebApp:
        return self.start()

    def __exit__(self, *_: object) -> None:
        self.close()


def _make_handler(app: WebApp) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            url = urlparse(self.path)
            query = parse_qs(url.query)
            if url.path == "/results":
                page = int(query.get("page", ["1"])[0])
                app.page = page
                body = render_page(app.kind, app.variant, page, app.edited)
            elif url.path == "/click":
                app.edited = query.get("key", [""])[0]
                body = "ok"
            elif url.path == "/state":
                body = f"edited={app.edited or 'none'}"
            else:
                self.send_error(404)
                return
            encoded = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, format: str, *args: object) -> None:
            """Stay silent: the lab prints its own metrics."""

    return Handler


class _ElementCollector(HTMLParser):
    """Collect interactive elements with the context a recorder would see."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.elements: list[dict[str, object]] = []
        self._ancestors: list[dict[str, object]] = []
        self._open: dict[str, object] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key: value or "" for key, value in attrs}
        if self._open is not None and tag == "br":
            return
        if tag in INTERACTIVE_TAGS and self._open is None:
            container = self._container_label()
            self._open = {
                "tag": tag,
                "attrs": attributes,
                "text": "",
                "container": container,
            }
        else:
            self._ancestors.append({"tag": tag, "attrs": attributes})

    def handle_endtag(self, tag: str) -> None:
        if self._open is not None and self._open["tag"] == tag:
            self.elements.append(self._open)
            self._open = None
            return
        if self._ancestors and self._ancestors[-1]["tag"] == tag:
            self._ancestors.pop()

    def handle_data(self, data: str) -> None:
        if self._open is not None:
            self._open["text"] = str(self._open["text"]) + data

    def _container_label(self) -> str | None:
        """The nearest ancestor's accessible name, as a recorder would record it."""
        for ancestor in reversed(self._ancestors):
            label = (
                ancestor["attrs"].get("aria-label") if isinstance(ancestor["attrs"], dict) else None
            )
            if isinstance(label, str) and label.strip():
                return label.strip()
        return None

    def close(self) -> None:
        super().close()

    def sited_elements(self) -> list[dict[str, object]]:
        """Elements with their document order position."""
        return self.elements


def _fetch(url: str) -> str:
    from urllib.request import urlopen

    with urlopen(url, timeout=5) as response:  # noqa: S310 - fixed local http URL
        return response.read().decode("utf-8")


class WebAdapter:
    """Adapter that turns variant pages into candidates and performs clicks."""

    surface_kind = "WEB"

    def __init__(self, app: WebApp, kind: str) -> None:
        self._app = app
        self._kind = kind
        self._variant = "A"
        self._page = 1

    def prepare(self, variant: str) -> None:
        """Put the app into one variant's start state."""
        self._variant = variant
        self._page = 1
        self._app.reset(variant)

    def snapshot(self, variant: str, row_rule: str | None = None) -> tuple[Candidate, ...]:
        """Observe the current page, following list pages when a row rule is set."""
        del variant
        self._page = 1
        html = self._fetch_page(self._page)
        if row_rule:
            html = self._page_containing(html, row_rule)
        return self._candidates(html)

    def truth_id(self, variant: str) -> str | None:
        """The element the person meant in this variant (lab-side ground truth)."""
        if self._kind == "rows":
            return "edit-1042"
        return {"A": "edit-1042", "B": "edit-1042", "C": None, "D": "edit-1099"}.get(variant)

    def perform(self, candidate: Candidate) -> None:
        """Click one candidate by asking the app to record that element."""
        _fetch(f"{self._app.base_url}/click?key={candidate.candidate_id}")

    def observe(self) -> str:
        """The observable outcome of the run so far."""
        return _fetch(f"{self._app.base_url}/state")

    def _fetch_page(self, page: int) -> str:
        return _fetch(f"{self._app.base_url}/results?page={page}")

    def _page_containing(self, html: str, row_rule: str) -> str:
        """Follow "next page" links (bounded) until the row rule appears."""
        current = html
        rule = row_rule.casefold()
        for _ in range(MAX_PAGES - 1):
            if rule in current.casefold():
                return current
            if 'data-key="next-page"' not in current:
                return current
            self._page += 1
            current = self._fetch_page(self._page)
        return current

    def _candidates(self, html: str) -> tuple[Candidate, ...]:
        collector = _ElementCollector()
        collector.feed(html)
        collector.close()
        candidates: list[Candidate] = []
        for ordinal, element in enumerate(collector.elements):
            attributes = element["attrs"]
            assert isinstance(attributes, dict)
            key = str(attributes.get("data-key", ""))
            if not key:
                continue
            candidates.append(
                Candidate(
                    candidate_id=key,
                    clues=_clues(
                        attributes, str(element["text"]).strip(), element["container"], ordinal
                    ),
                    ordinal=ordinal,
                    enabled="disabled" not in attributes,
                    position=(10, ordinal * 24),
                )
            )
        return tuple(candidates)


def _clues(
    attributes: dict[str, str],
    text: str,
    container: object,
    ordinal: int,
) -> tuple[Clue, ...]:
    """Build the clue bundle a recorder would have captured for this element."""
    clues: list[Clue] = []
    dom_id = attributes.get("id")
    if dom_id:
        clues.append(Clue(ClueKind.DOM_ID, dom_id, "id"))
    clues.append(
        Clue(ClueKind.ROLE, attributes.get("tag", attributes.get("role", "button")), "role")
    )
    if text:
        clues.append(Clue(ClueKind.NAME, text, "name"))
    if isinstance(container, str) and container:
        clues.append(Clue(ClueKind.CONTAINER_TEXT, container, "container"))
    clues.append(Clue(ClueKind.DOMAIN, HOST, "app"))
    clues.append(Clue(ClueKind.ORDINAL, str(ordinal), "ordinal"))
    return tuple(clues)
