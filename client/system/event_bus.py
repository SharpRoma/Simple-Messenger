import asyncio
import logging
from typing import Callable, Any, Dict, List

logger = logging.getLogger("messenger.event_bus")


class EventBus:
    def __init__(self):
        # Словарь: { "event_type": [callback1, callback2, ...] }
        self._subscribers: Dict[str, List[Callable[[Any], Any]]] = {}

    def subscribe(self, event_type: str, callback: Callable[[Any], Any]):
        """Подписка на определенный тип событий."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        if callback not in self._subscribers[event_type]:
            self._subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: str, callback: Callable[[Any], Any]):
        """Отписка от определенного типа событий."""
        if event_type in self._subscribers:
            if callback in self._subscribers[event_type]:
                self._subscribers[event_type].remove(callback)
            if not self._subscribers[event_type]:
                del self._subscribers[event_type]

    async def publish(self, event_type: str, data: Any = None):
        """Публикация события. Все обработчики запускаются параллельно."""
        if event_type not in self._subscribers:
            return

        tasks = []
        for callback in list(self._subscribers[event_type]):
            try:
                if asyncio.iscoroutinefunction(callback):
                    tasks.append(callback(data))
                else:
                    callback(data)
            except Exception as e:
                logger.error(f"Error executing callback for event '{event_type}': {e}", exc_info=True)

        if tasks:
            # Запускаем все асинхронные обработчики параллельно и перехватываем исключения
            await asyncio.gather(*tasks, return_exceptions=True)
