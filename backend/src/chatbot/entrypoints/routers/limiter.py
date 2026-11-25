from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

# Shared slowapi limiter — registered on the app in main.py, applied to the
# login route in routers/auth.py. Keyed by client IP.
limiter = Limiter(key_func=get_remote_address)
