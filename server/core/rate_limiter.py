import time
from collections import defaultdict
from fastapi import HTTPException, Request, status


class InMemoryRateLimiter:
    def __init__(self, requests_limit: int, window_seconds: int):
        self.requests_limit = requests_limit
        self.window_seconds = window_seconds
        self.history = defaultdict(list)

    async def __call__(self, request: Request):
        ip = request.client.host if request.client else "127.0.0.1"
        now = time.time()
        
        # Фильтруем историю запросов, оставляя только те, что попали в скользящее окно
        self.history[ip] = [t for t in self.history[ip] if now - t < self.window_seconds]
        
        if len(self.history[ip]) >= self.requests_limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Слишком много запросов. Пожалуйста, попробуйте позже."
            )
            
        self.history[ip].append(now)

    def clear(self):
        self.history.clear()

