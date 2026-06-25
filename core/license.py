from __future__ import annotations

import datetime
import secrets
from typing import Final

from .hardware import get_fingerprint_hash



LICENSED_FINGERPRINT: Final[str] = (
    "1416617f4829ffa5f633f4ef56d7322c86e217c477869163b8068a1e1663c841"
)

START_DATE: Final[str] = "2026-05-23"

END_DATE: Final[str] = "2026-07-08"


_ERROR_MESSAGE: Final[str] = (
    "This copy of the application is not licensed for this device."
)


def _die(message: str = _ERROR_MESSAGE) -> None:
    raise SystemExit(message)


def validate_or_exit() -> None:
    """
    Validate device fingerprint and license dates.
    """

    try:
        current_fingerprint = get_fingerprint_hash()
    except Exception:
        _die()

    
    if not secrets.compare_digest(
        current_fingerprint,
        LICENSED_FINGERPRINT
    ):
        _die()

    
    try:
        start_date = datetime.date.fromisoformat(START_DATE)
        end_date = datetime.date.fromisoformat(END_DATE)
    except Exception:
        _die("Invalid license dates.")

    today = datetime.date.today()

    if today < start_date:
        _die("License not active yet.")

    if today > end_date:
        _die("Trial period expired. Please contact the vendor in 0661345595.")

    return True