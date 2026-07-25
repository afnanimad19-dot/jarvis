"""WhatsApp messaging via pywhatkit (WhatsApp Web automation).

Honest reality: WhatsApp has no free official API for personal accounts.
pywhatkit works by opening web.whatsapp.com in your default browser and
typing the message — so you must be logged in to WhatsApp Web there, the
browser will visibly open, and it takes ~15-25 seconds per message. Clunky
but free. (The official Business Cloud API is the clean path if you ever
want it.)

Setup:
1. pip install pywhatkit
2. Log in to web.whatsapp.com in your default browser once.
3. Contacts in jarvis_hud/.env (name:number with country code, comma-sep):
       JARVIS_WA_CONTACTS=mom:+971501234567,ali:+971559876543

Then: "Jarvis, whatsapp to mom: I'll be home late" -> JARVIS asks you to
confirm before sending. Nothing is ever sent without your confirmation.
"""

import os


def contacts() -> dict:
    out = {}
    raw = os.environ.get("JARVIS_WA_CONTACTS", "")
    for pair in raw.split(","):
        if ":" in pair:
            name, number = pair.split(":", 1)
            out[name.strip().lower()] = number.strip()
    return out


def resolve(to: str) -> str:
    to = to.strip()
    if to.startswith("+") and to[1:].replace(" ", "").isdigit():
        return to.replace(" ", "")
    number = contacts().get(to.lower())
    if not number:
        known = ", ".join(contacts()) or "none configured"
        raise RuntimeError(f"Unknown contact {to!r}. Known contacts: {known}. "
                           "Add them to JARVIS_WA_CONTACTS in .env or say a full +number.")
    return number


def send(to: str, text: str) -> str:
    number = resolve(to)
    try:
        import pywhatkit
    except ImportError as exc:
        raise RuntimeError("WhatsApp needs pywhatkit: pip install pywhatkit "
                           "(and log in to web.whatsapp.com once).") from exc
    pywhatkit.sendwhatmsg_instantly(number, text, wait_time=25, tab_close=True, close_time=4)
    return number
