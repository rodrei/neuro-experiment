# -*- coding: utf-8 -*-
"""
The team's view of the saved sessions: list them, read them, download them.

Everything here is server-rendered HTML with no JavaScript, and everything a
participant wrote goes through `_e`, so their text can never run in the team's
browser. app.py checks the password before calling `handle`.

  /admin                          the list of sessions
  /admin/all.zip                  every session, without the browser checks
  /admin/session/<base>           one session: conversations, responses, files
  /admin/session/<base>.zip       one session's four files
  /admin/file/<base>_<kind>.csv   one file

Paths are matched against a pattern with no dots or slashes and then have to
exist, so a crafted path cannot reach anything outside the data folder.

The page text is in Spanish, for the team. Standard library only.
"""

import csv
import html
import io
import os
import re
import zipfile

KINDS = ("responses", "behavioral", "chat", "events")
KIND_LABELS = {"responses": "respuestas", "behavioral": "conducta por episodio",
               "chat": "conversaciones", "events": "marcadores"}
# What the browser check calls its sessions (see web/e2e/run_flow.mjs).
CHECK_PREFIX = "S1_check-"

_BASE = r"S1_[A-Za-z0-9_-]+"
_SESSION = re.compile(r"/admin/session/(%s)" % _BASE)
_SESSION_ZIP = re.compile(r"/admin/session/(%s)\.zip" % _BASE)
_FILE = re.compile(r"/admin/file/(%s)_(%s)\.csv" % (_BASE, "|".join(KINDS)))
_STAMP = re.compile(r"_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})$")

HTML_TYPE = "text/html; charset=utf-8"
CSV_TYPE = "text/csv; charset=utf-8"
ZIP_TYPE = "application/zip"

# A participant's text can be long, and csv refuses fields over 128 KB by default.
csv.field_size_limit(10 * 1024 * 1024)

STYLE = """
body { font-family: system-ui, sans-serif; margin: 2rem auto; max-width: 70rem;
       padding: 0 1rem; color: #1a1a1a; }
a { color: #2f6fc4; }
table { border-collapse: collapse; width: 100%; font-size: .92rem; }
th, td { border-bottom: 1px solid #ddd; padding: .4rem .6rem; text-align: left;
         vertical-align: top; }
th { color: #666; font-weight: 600; }
td.value { white-space: pre-wrap; overflow-wrap: anywhere; }
.muted { color: #777; }
.check td { color: #999; }
.button { display: inline-block; margin: 0 .5rem .5rem 0; padding: .35rem .8rem;
          border: 1px solid #2f6fc4; border-radius: 6px; text-decoration: none; }
.message { margin: .5rem 0; padding: .5rem .8rem; border-radius: 8px;
           background: #f1f2f4; white-space: pre-wrap; overflow-wrap: anywhere; }
.message.participant { background: #dce8f8; }
.meta { font-size: .78rem; color: #666; margin-bottom: .2rem; }
details { margin: 1.5rem 0; }
summary { cursor: pointer; font-weight: 600; }
"""


def _e(value):
    return html.escape("" if value is None else str(value), quote=True)


def _path(folder, base, kind):
    return os.path.join(folder, "%s_%s.csv" % (base, kind))


def _rows(folder, base, kind):
    """The rows of a file as dicts; missing or empty files give no rows."""
    try:
        with open(_path(folder, base, kind), newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    except FileNotFoundError:
        return []


def _responses(folder, base):
    """The key,value file, which has no header, in file order."""
    with open(_path(folder, base, "responses"), newline="", encoding="utf-8") as f:
        return [(row[0], row[1]) for row in csv.reader(f) if len(row) == 2]


def _number(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _when(base):
    m = _STAMP.search(base)
    if not m:
        return ""
    return "%s-%s-%s %s:%s:%s" % m.groups()


def _bases(folder):
    """Every saved session, newest first."""
    suffix = "_responses.csv"
    try:
        names = os.listdir(folder)
    except FileNotFoundError:
        return []
    bases = [n[:-len(suffix)] for n in names if n.endswith(suffix)]
    return sorted((b for b in bases if re.fullmatch(_BASE, b)),
                  key=_when, reverse=True)


def _summary(folder, base):
    responses = dict(_responses(folder, base))
    behavioral = _rows(folder, base, "behavioral")
    return {
        "base": base,
        "id": responses.get("participant_id") or base,
        "when": _when(base),
        "mode": responses.get("mode", ""),
        "sequence": responses.get("sequence", ""),
        "episodes": len(behavioral),
        "rounds": sum(_number(r.get("rounds_completed")) for r in behavioral),
        "fallback": sum(_number(r.get("fallback_turns")) for r in behavioral),
        "check": base.startswith(CHECK_PREFIX),
    }


def _page(title, body):
    return ("<!doctype html><html lang='es'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'>"
            "<title>%s</title><style>%s</style></head><body>%s</body></html>"
            % (_e(title), STYLE, body))


def _list_page(folder):
    sessions = [_summary(folder, b) for b in _bases(folder)]
    real = sum(1 for s in sessions if not s["check"])
    head = "<h1>Sesiones guardadas</h1>"
    if not sessions:
        return _page("Sesiones", head + "<p>Todavía no hay sesiones guardadas.</p>")
    rows = []
    for s in sessions:
        rows.append(
            "<tr class='%s'><td>%s</td><td>%s%s</td><td>%s</td><td>%s</td>"
            "<td>%s de 4</td><td>%s de 12</td><td>%s</td>"
            "<td><a href='/admin/session/%s'>Ver</a> · "
            "<a href='/admin/session/%s.zip'>Descargar</a></td></tr>" % (
                "check" if s["check"] else "", _e(s["when"]), _e(s["id"]),
                " <span class='muted'>(prueba)</span>" if s["check"] else "",
                _e(s["mode"]), _e(s["sequence"]), s["episodes"], s["rounds"],
                s["fallback"], s["base"], s["base"]))
    body = (head
            + "<p>%d sesiones. Las pruebas automáticas se marcan como «prueba» "
              "y no entran en la descarga completa.</p>" % real
            + "<p><a class='button' href='/admin/all.zip'>Descargar todo (.zip)</a></p>"
            + "<table><tr><th>Fecha (UTC)</th><th>ID</th><th>Modo</th>"
              "<th>Secuencia</th><th>Episodios</th><th>Rondas</th>"
              "<th>Turnos de respaldo</th><th></th></tr>"
            + "".join(rows) + "</table>")
    return _page("Sesiones", body)


def _conversations(folder, base):
    """The transcript, one section per episode."""
    episodes = {}
    for row in _rows(folder, base, "chat"):
        episodes.setdefault(_number(row.get("episode")), []).append(row)
    if not episodes:
        return "<p class='muted'>Esta sesión no tiene mensajes.</p>"
    parts = []
    for episode in sorted(episodes):
        rows = sorted(episodes[episode], key=lambda r: _number(r.get("turn")))
        first = rows[0]
        parts.append("<h3>Episodio %d · %s · %s</h3>" % (
            episode, _e(first.get("condition")), _e(first.get("domain"))))
        for row in rows:
            participant = row.get("author") == "participant"
            parts.append(
                "<div class='message %s'><div class='meta'>%s · ronda %s · %s</div>%s</div>"
                % ("participant" if participant else "agent",
                   "Participante" if participant else "Interlocutor",
                   _e(row.get("round")), _e(row.get("origin")), _e(row.get("text"))))
    return "".join(parts)


def _table(rows, columns):
    head = "".join("<th>%s</th>" % _e(c) for c in columns)
    body = "".join(
        "<tr>%s</tr>" % "".join("<td class='value'>%s</td>" % _e(row.get(c))
                                for c in columns)
        for row in rows)
    return "<table><tr>%s</tr>%s</table>" % (head, body)


def _session_page(folder, base):
    summary = _summary(folder, base)
    links = "".join(
        "<a class='button' href='/admin/file/%s_%s.csv'>%s (.csv)</a>"
        % (base, kind, KIND_LABELS[kind]) for kind in KINDS)
    responses = "".join(
        "<tr><td>%s</td><td class='value'>%s</td></tr>" % (_e(k), _e(v))
        for k, v in _responses(folder, base))
    events = _rows(folder, base, "events")
    body = (
        "<p><a href='/admin'>← Todas las sesiones</a></p>"
        "<h1>Sesión %s</h1><p class='muted'>%s UTC · %s · secuencia %s</p>"
        % (_e(summary["id"]), _e(summary["when"]), _e(summary["mode"]),
           _e(summary["sequence"]))
        + "<p><a class='button' href='/admin/session/%s.zip'>Descargar la sesión (.zip)</a>%s</p>"
        % (base, links)
        + "<h2>Conversaciones</h2>" + _conversations(folder, base)
        + "<details open><summary>Respuestas</summary>"
          "<table><tr><th>Campo</th><th>Valor</th></tr>%s</table></details>" % responses
        + "<details><summary>Marcadores (%d)</summary>%s</details>" % (
            len(events), _table(events, ["t_experiment_s", "label", "detail"])))
    return _page("Sesión", body)


def _zip(folder, bases):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for base in bases:
            for kind in KINDS:
                path = _path(folder, base, kind)
                if os.path.isfile(path):
                    archive.write(path, os.path.basename(path))
    return buffer.getvalue()


def handle(path, folder):
    """Returns (status, body, content type, download name or None)."""
    not_found = (404, _page("No encontrado", "<p>No encontrado.</p>"), HTML_TYPE, None)

    if path in ("/admin", "/admin/"):
        return 200, _list_page(folder), HTML_TYPE, None

    if path == "/admin/all.zip":
        bases = [b for b in _bases(folder) if not b.startswith(CHECK_PREFIX)]
        return 200, _zip(folder, bases), ZIP_TYPE, "sesiones.zip"

    match = _SESSION_ZIP.fullmatch(path)
    if match:
        base = match.group(1)
        if not os.path.isfile(_path(folder, base, "responses")):
            return not_found
        return 200, _zip(folder, [base]), ZIP_TYPE, base + ".zip"

    match = _SESSION.fullmatch(path)
    if match:
        base = match.group(1)
        if not os.path.isfile(_path(folder, base, "responses")):
            return not_found
        return 200, _session_page(folder, base), HTML_TYPE, None

    match = _FILE.fullmatch(path)
    if match:
        target = _path(folder, match.group(1), match.group(2))
        if not os.path.isfile(target):
            return not_found
        with open(target, "rb") as f:
            return 200, f.read(), CSV_TYPE, os.path.basename(target)

    return not_found
