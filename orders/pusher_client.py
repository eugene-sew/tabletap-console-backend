"""Lazy Pusher client — instantiated on first use so the module
can be imported even before `pip install pusher` runs at container
build time."""
_client = None

def get_pusher_client():
    global _client
    if _client is None:
        try:
            import pusher
            from django.conf import settings
            _client = pusher.Pusher(
                app_id=settings.PUSHER_APP_ID,
                key=settings.PUSHER_KEY,
                secret=settings.PUSHER_SECRET,
                cluster=settings.PUSHER_CLUSTER,
                ssl=True,
            )
        except Exception as e:
            print(f"[Pusher] Could not initialise client: {e}")
    return _client
