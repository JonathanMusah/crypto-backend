# WebSocket Setup for Real-Time Messaging

## Current Status

The messaging system has WebSocket support implemented, but **Django's `runserver` does NOT support WebSockets**. 

## To Enable WebSockets

You need to run Django with an ASGI server instead of `runserver`:

### Option 1: Using Daphne (Recommended)

1. Install daphne:
```bash
pip install daphne
```

2. Run the server:
```bash
daphne -b 0.0.0.0 -p 8000 config.asgi:application
```

### Option 2: Using Uvicorn

1. Install uvicorn:
```bash
pip install uvicorn[standard]
```

2. Run the server:
```bash
uvicorn config.asgi:application --host 0.0.0.0 --port 8000
```

## Production Setup

For production, you should:

1. **Use Redis for Channel Layers** (instead of InMemoryChannelLayer):
```bash
pip install channels-redis
```

2. Update `settings.py`:
```python
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [('127.0.0.1', 6379)],
        },
    },
}
```

3. Run with a process manager like **supervisord** or **systemd**

## Current Behavior

- **With `runserver`**: WebSocket connections will fail, but the app still works with polling (messages refresh every few seconds)
- **With ASGI server**: WebSocket connections work, providing real-time messaging

## Testing WebSockets

1. Start the server with daphne/uvicorn
2. Open two browser windows with different accounts
3. Send a message - it should appear instantly in the other window
4. Start typing - the other user should see "User is typing..."

## Troubleshooting

- **WebSocket connection fails**: Make sure you're using daphne/uvicorn, not runserver
- **Messages not appearing in real-time**: Check browser console for WebSocket errors
- **Typing indicators not working**: Verify WebSocket connection is established (check browser console)

