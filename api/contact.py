"""The contact form's endpoint: takes the POST from /contact/ and mails it on.

Vercel deploys this file as /api/contact. Standard library only, so there is
no requirements.txt and nothing here to keep up to date.

Set in the Vercel project's environment variables:

    RESEND_API_KEY   required. Without it the form reports that it is not
                     connected rather than losing a submission quietly.
    CONTACT_TO       where submissions land   (default editor@explorelyons.com)
    CONTACT_FROM     the verified sender      (default form@explorelyons.com)

CONTACT_FROM has to be on a domain verified in Resend, which means adding the
DKIM and SPF records it gives you to explorelyons.com's DNS. Until that is
done Resend will only deliver to the address that owns the account.
"""
import json
import os
import re
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler

RESEND_URL = "https://api.resend.com/emails"
TO = os.environ.get("CONTACT_TO", "editor@explorelyons.com")
FROM = os.environ.get("CONTACT_FROM", "ExploreLyons.com <form@explorelyons.com>")
EDITOR = "editor@explorelyons.com"

# Long enough for a real correction and its source, short enough that this is
# not somewhere to paste a novel. A submission over a limit is refused rather
# than truncated, so nobody is told their correction was sent when half of it
# was thrown away.
LIMITS = {"kind": 80, "subject": 200, "page": 200, "source": 500, "email": 200, "detail": 4000}
MAX_BODY = 16 * 1024
EMAIL_RE = re.compile(r"^[^@\s,<>]+@[^@\s,<>]+\.[A-Za-z]{2,}$")


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_BODY:
            return self._reply(400, "That submission was empty, or too large to accept.")

        raw = self.rfile.read(length).decode("utf-8", "replace")
        fields = {k: (v[0] or "").strip()
                  for k, v in urllib.parse.parse_qs(raw, keep_blank_values=True).items()}

        # The hidden field no person can see. A bot fills in everything it
        # finds; it is answered exactly as a success is, so it learns nothing
        # from the response and nothing is sent.
        if fields.get("_gotcha"):
            return self._reply(200, None)

        subject, detail = fields.get("subject", ""), fields.get("detail", "")
        if not subject or not detail:
            return self._reply(400, "A name and some detail are both needed.")
        for name, cap in LIMITS.items():
            if len(fields.get(name, "")) > cap:
                return self._reply(400, f"The {name} field is longer than {cap} characters.")

        key = os.environ.get("RESEND_API_KEY")
        if not key:
            return self._reply(503, "The form is not connected to its mail service yet.")

        sender = fields.get("email", "")
        body = "\n".join([
            f"Kind:   {fields.get('kind') or '(not given)'}",
            f"Name:   {subject}",
            f"Page:   {fields.get('page') or '(not given)'}",
            f"Source: {fields.get('source') or '(none given)'}",
            f"Reply:  {sender or '(no address given)'}",
            "",
            detail,
            "",
            "-- ",
            "Sent by the form at https://explorelyons.com/contact/",
        ])
        payload = {
            "from": FROM,
            "to": [TO],
            "subject": f"[ExploreLyons] {fields.get('kind') or 'Submission'}: {subject}"[:200],
            "text": body,
        }
        # Only a clean address: a malformed one makes Resend reject the whole
        # request, which would lose a submission over a typo in an optional field.
        if EMAIL_RE.match(sender):
            payload["reply_to"] = [sender]

        request = urllib.request.Request(
            RESEND_URL,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                response.read()
        except Exception:
            # Deliberately not repeating the upstream error: it can carry the
            # request that was sent, and the visitor can do nothing with it.
            return self._reply(502, "The mail service would not take that just now.")
        return self._reply(200, None)

    def do_GET(self):
        self._reply(405, "This address only takes the contact form's submission. "
                         "The form itself is at /contact/.")

    def _reply(self, status, message):
        """JSON when the page asked for it, a redirect to /thanks/ otherwise.

        The redirect target is fixed here on purpose. Reading it from the
        request -- which is how the usual form services do it -- would turn
        this into an open redirect that anyone could point anywhere."""
        if "application/json" in (self.headers.get("Accept") or ""):
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            out = {"ok": status == 200}
            if message:
                out["error"] = message
            self.wfile.write(json.dumps(out).encode("utf-8"))
            return
        if status == 200:
            self.send_response(303)
            self.send_header("Location", "/thanks/")
            self.end_headers()
            return
        # Plain text means nobody is running the page's scripting, so this is
        # the whole of what they will see: it has to carry the way out too.
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        text = (message or "That did not send.") + f" Write to {EDITOR} instead."
        self.wfile.write(text.encode("utf-8"))

    def log_message(self, *args):
        """Vercel captures stdout as function logs, and a submission is
        somebody's email address and their words. Only failures are worth a
        line, and those are logged where they happen."""
