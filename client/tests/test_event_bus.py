import pytest
import asyncio
from system.event_bus import EventBus


@pytest.mark.asyncio
async def test_event_bus_sync_subscription():
    eb = EventBus()
    received_data = []

    def callback(data):
        received_data.append(data)

    # Подписываемся на событие "test_event"
    eb.subscribe("test_event", callback)

    # Публикуем событие
    await eb.publish("test_event", {"value": 42})
    
    assert len(received_data) == 1
    assert received_data[0]["value"] == 42


@pytest.mark.asyncio
async def test_event_bus_async_subscription():
    eb = EventBus()
    received_data = []

    async def async_callback(data):
        await asyncio.sleep(0.01)
        received_data.append(data)

    eb.subscribe("async_event", async_callback)
    await eb.publish("async_event", "hello_async")

    assert len(received_data) == 1
    assert received_data[0] == "hello_async"


@pytest.mark.asyncio
async def test_event_bus_multiple_subscribers():
    eb = EventBus()
    results = []

    def handler_one(data):
        results.append(data + "_one")

    async def handler_two(data):
        await asyncio.sleep(0.01)
        results.append(data + "_two")

    eb.subscribe("multi_event", handler_one)
    eb.subscribe("multi_event", handler_two)

    await eb.publish("multi_event", "test")

    # Проверяем, что вызвались оба обработчика
    assert len(results) == 2
    assert "test_one" in results
    assert "test_two" in results


@pytest.mark.asyncio
async def test_event_bus_unsubscribe():
    eb = EventBus()
    received_data = []

    def callback(data):
        received_data.append(data)

    eb.subscribe("temp_event", callback)
    await eb.publish("temp_event", "first")
    
    # Отписываемся
    eb.unsubscribe("temp_event", callback)
    await eb.publish("temp_event", "second")

    # Должен быть только первый вызов
    assert len(received_data) == 1
    assert received_data[0] == "first"
