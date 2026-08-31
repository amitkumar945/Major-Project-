"""
SMTP self-test.

Validates the MAIL_* values in `backend/.env` without touching the rest of the
app, so email can be set up and confirmed in one step.

    python check_email.py                  # check config + connect/login
    python check_email.py you@example.com  # also send a real test message

Exit code is 0 when everything the run attempted succeeded, 1 otherwise, so it
can be used in a setup script. The password is never printed.
"""

import logging
import sys

from app import create_app
from services import email_service

# The service logs the useful detail (which key is missing, which SMTP code
# came back) at INFO/ERROR; surface it rather than swallowing it.
logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")


def _print_config(config: dict) -> None:
    print("\nConfiguration (backend/.env)")
    print("-" * 46)
    for key, value in config.items():
        print(f"  {key:<12} {value}")


def _hint(reason: str) -> str:
    """Point at the specific thing to change for this failure."""
    return {
        "config": (
            "Set MAIL_ENABLED=true and fill MAIL_SERVER / MAIL_USERNAME /\n"
            "  MAIL_PASSWORD in backend/.env."
        ),
        "auth": (
            "The server rejected the credentials. For Gmail this must be a\n"
            "  16-character App Password (2-Step Verification on):\n"
            "  https://myaccount.google.com/apppasswords\n"
            "  A normal account password will always fail with code 535."
        ),
        "connect": (
            "Could not reach the server. Check MAIL_SERVER / MAIL_PORT and\n"
            "  whether a firewall or network blocks outbound SMTP."
        ),
        "tls": (
            "TLS negotiation failed. Use port 587 with MAIL_USE_TLS=true, or\n"
            "  port 465 with MAIL_USE_SSL=true - not both."
        ),
        "timeout": "The server did not respond. Raise MAIL_TIMEOUT or check the network.",
        "recipient": "The recipient address was rejected. Check the address.",
    }.get(reason, "See the log line above for the underlying SMTP error.")


def main() -> int:
    recipient = sys.argv[1].strip() if len(sys.argv) > 1 else ""

    app = create_app()
    with app.app_context():
        config = email_service.describe_config()
        _print_config(config)

        if not config["enabled"]:
            print("\nFAIL  MAIL_ENABLED is false - email is turned off.")
            print("      " + _hint("config"))
            return 1

        if config["placeholders"]:
            keys = " and ".join(config["placeholders"])
            print(f"\nFAIL  {keys} still hold the .env.example placeholder value(s).")
            print(
                "      Edit backend/.env and replace them:\n"
                "        MAIL_USERNAME=<your real gmail address>\n"
                "        MAIL_PASSWORD=<16-character App Password, no spaces>\n"
                "      Create the App Password (2-Step Verification must be on):\n"
                "        https://myaccount.google.com/apppasswords\n"
                "      Then run this script again."
            )
            return 1

        if not config["configured"]:
            print("\nFAIL  Mail is enabled but the settings are incomplete.")
            print("      " + _hint("config"))
            return 1

        if config["suppressed"]:
            print(
                "\nNOTE  MAIL_SUPPRESS_SEND=true - the send path runs but no\n"
                "      socket is opened and no mail leaves. Set it to false\n"
                "      for a real delivery test."
            )

        # ------------------------------------------------ connect and log in
        print("\nConnecting to the SMTP server ...")
        try:
            email_service.verify_connection()
        except email_service.EmailError as exc:
            print(f"\nFAIL  {exc.message}  (reason: {exc.reason})")
            print("      " + _hint(exc.reason))
            return 1
        print("OK    Connected and authenticated.")

        # ------------------------------------------------------ send a test
        if not recipient:
            print(
                "\nDone. Pass an address to also send a real test message:\n"
                "  python check_email.py you@example.com"
            )
            return 0

        print(f"\nSending a test message to {recipient} ...")
        try:
            email_service.send_email(
                recipient,
                "DSVV Grievance Portal - SMTP test",
                "This is a test message. Your SMTP settings are working.",
                "<p>This is a test message. Your SMTP settings are "
                "<strong>working</strong>.</p>",
            )
        except email_service.EmailError as exc:
            print(f"\nFAIL  {exc.message}  (reason: {exc.reason})")
            print("      " + _hint(exc.reason))
            return 1

        print("OK    Test message sent. Check the inbox (and the spam folder).")
        return 0


if __name__ == "__main__":
    sys.exit(main())
