from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Callable, Type

from Skynet.core.events import BaseEvent

SubscriptionToken = str


class EventBus:
    def __init__(self) -> None:
        # Map: event_type -> {token: callback}
        self._subscribers: dict[type, dict[str, Callable]] = defaultdict(dict)

    def subscribe(self, event_type: Type[BaseEvent], callback: Callable) -> SubscriptionToken:
        token = str(uuid.uuid4())
        self._subscribers[event_type][token] = callback
        return token

    def unsubscribe(self, token: SubscriptionToken) -> None:
        for callbacks in self._subscribers.values():
            callbacks.pop(token, None)

    def publish(self, event: BaseEvent) -> None:
        if not isinstance(event, BaseEvent):
            raise TypeError(
                f"EventBus.publish requires a BaseEvent subclass, got {type(event)}"
            )
        for callback in list(self._subscribers.get(type(event), {}).values()):
            callback(event)
