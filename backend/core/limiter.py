"""
Shared slowapi Limiter instance.

Import `limiter` in route files and use @limiter.limit("N/period") decorator.
The instance is registered on app.state in main.py.
"""
try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address
    limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
    RATE_LIMIT_AVAILABLE = True
except ImportError:
    # Fallback no-op decorator when slowapi is not installed
    import functools

    class _NoopLimiter:
        def limit(self, *args, **kwargs):
            def decorator(fn):
                @functools.wraps(fn)
                async def wrapper(*a, **kw):
                    return await fn(*a, **kw)
                return wrapper
            return decorator

    limiter = _NoopLimiter()  # type: ignore[assignment]
    RATE_LIMIT_AVAILABLE = False
