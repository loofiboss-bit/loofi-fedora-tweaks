"""
EventBus — v20.0 Phase 2 (Agent Hive Mind).

Thread-safe pub/sub system enabling inter-agent communication and system event reactions.
Subscribers execute asynchronously to prevent blocking. Failed subscribers are logged but
do not crash the EventBus.
"""

from __future__ import annotations

import logging
import threading
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Event:
    """
    Structured event payload.

    Attributes:
        topic: Event topic string (e.g., "system.power.battery").
        data: Arbitrary payload dictionary.
        source: Optional identifier of the event emitter.
    """

    topic: str
    data: Dict[str, Any]
    source: Optional[str] = None

    def __post_init__(self):
        """Validate event structure."""
        if not self.topic:
            raise ValueError("Event topic cannot be empty")
        if not isinstance(self.data, dict):
            raise TypeError(f"Event data must be dict, got {type(self.data)}")


@dataclass
class Subscription:
    """
    Internal subscription record.

    Attributes:
        topic: Event topic to subscribe to.
        callback: Callable invoked when topic is published.
        subscriber_id: Optional identifier for debugging.
    """

    topic: str
    callback: Callable[[Event], None]
    subscriber_id: Optional[str] = None


class EventBus:
    """
    Thread-safe singleton pub/sub event bus.

    Enables agents to subscribe to system events and react to other agents' actions.
    All subscriber callbacks execute asynchronously in a thread pool to prevent blocking.

    Standard Topics (from v20.0 roadmap):
        - system.power.battery (level, status)
        - system.thermal.throttling (temp, sensor)
        - security.firewall.panic (source)
        - agent.{agent_id}.success (action_result)
        - agent.{agent_id}.failure (error_log)
        - system.storage.low (path, available_mb)
        - network.connection.public (ssid, security)
    """

    _instance: Optional[EventBus] = None
    _lock = threading.Lock()

    def __new__(cls) -> EventBus:
        """Singleton pattern — only one EventBus instance per process."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize EventBus with thread-safe structures."""
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self._subscriptions: Dict[str, List[Subscription]] = {}
        self._sub_lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="EventBus")
        self._futures: set[Future[None]] = set()
        self._accepting_publishes = True
        logger.info("EventBus initialized")

    def subscribe(
        self, topic: str, callback: Callable[[Event], None], subscriber_id: Optional[str] = None
    ) -> None:
        """
        Subscribe to an event topic.

        Args:
            topic: Event topic string (e.g., "system.power.battery").
            callback: Function invoked when topic is published. Signature: callback(event: Event).
            subscriber_id: Optional identifier for debugging and logging.

        Raises:
            ValueError: If topic is empty or callback is not callable.
        """
        if not topic:
            raise ValueError("Topic cannot be empty")
        if not callable(callback):
            raise TypeError(f"Callback must be callable, got {type(callback)}")

        subscription = Subscription(topic=topic, callback=callback, subscriber_id=subscriber_id)

        with self._sub_lock:
            if not self._accepting_publishes:
                raise RuntimeError("EventBus is shut down")
            if topic not in self._subscriptions:
                self._subscriptions[topic] = []
            self._subscriptions[topic].append(subscription)

        logger.debug(
            "Subscribed to topic '%s' (subscriber_id=%s, total=%d)",
            topic,
            subscriber_id or "anonymous",
            len(self._subscriptions[topic]),
        )

    def publish(self, topic: str, data: Dict[str, Any], source: Optional[str] = None) -> None:
        """
        Publish an event to all subscribers of the topic.

        Subscribers are invoked asynchronously in a thread pool. Failed subscribers are
        logged but do not prevent other subscribers from executing.

        Args:
            topic: Event topic string.
            data: Event payload dictionary.
            source: Optional identifier of the event emitter.

        Raises:
            ValueError: If topic is empty.
            TypeError: If data is not a dict.
        """
        event = Event(topic=topic, data=data, source=source)
        logger.debug("Publishing event: topic='%s', source='%s'", topic, source or "unknown")

        with self._sub_lock:
            if not self._accepting_publishes:
                logger.debug("Discarding event after EventBus shutdown: topic='%s'", topic)
                return
            subscribers = self._subscriptions.get(topic, []).copy()

        if not subscribers:
            logger.debug("No subscribers for topic '%s'", topic)
            return

        for sub in subscribers:
            with self._sub_lock:
                if not self._accepting_publishes:
                    return
                future = self._executor.submit(self._invoke_subscriber, sub, event)
                self._futures.add(future)
            future.add_done_callback(self._discard_future)

    def _discard_future(self, future: Future[None]) -> None:
        """Forget a completed subscriber invocation."""
        with self._sub_lock:
            self._futures.discard(future)

    def _invoke_subscriber(self, subscription: Subscription, event: Event) -> None:
        """
        Internal: Invoke a single subscriber callback.

        Args:
            subscription: Subscription record.
            event: Event to pass to callback.
        """
        try:
            subscription.callback(event)
            logger.debug(
                "Subscriber invoked: topic='%s', subscriber_id='%s'",
                subscription.topic,
                subscription.subscriber_id or "anonymous",
            )
        except (RuntimeError, TypeError, ValueError, AttributeError) as e:
            logger.error(
                "Subscriber callback failed: topic='%s', subscriber_id='%s', error=%s",
                subscription.topic,
                subscription.subscriber_id or "anonymous",
                e,
                exc_info=True,
            )

    def unsubscribe(
        self, topic: str, callback: Callable[[Event], None], subscriber_id: Optional[str] = None
    ) -> bool:
        """
        Unsubscribe a specific callback from a topic.

        Args:
            topic: Event topic string.
            callback: The exact callback function to remove.
            subscriber_id: Optional subscriber ID for matching (if provided during subscribe).

        Returns:
            True if subscription was found and removed, False otherwise.
        """
        with self._sub_lock:
            if topic not in self._subscriptions:
                return False

            original_count = len(self._subscriptions[topic])
            self._subscriptions[topic] = [
                sub
                for sub in self._subscriptions[topic]
                if not (sub.callback == callback and (subscriber_id is None or sub.subscriber_id == subscriber_id))
            ]

            removed = original_count - len(self._subscriptions[topic])
            if removed > 0:
                logger.debug(
                    "Unsubscribed from topic '%s' (subscriber_id=%s, removed=%d)",
                    topic,
                    subscriber_id or "anonymous",
                    removed,
                )
                return True
            return False

    def clear(self) -> None:
        """
        Clear all subscriptions. Useful for testing.
        """
        with self._sub_lock:
            count = sum(len(subs) for subs in self._subscriptions.values())
            self._subscriptions.clear()
        logger.info("EventBus cleared: %d subscriptions removed", count)

    def get_subscriber_count(self, topic: str) -> int:
        """
        Get the number of subscribers for a topic.

        Args:
            topic: Event topic string.

        Returns:
            Number of subscribers for the topic.
        """
        with self._sub_lock:
            return len(self._subscriptions.get(topic, []))

    def shutdown(self, timeout: float = 5.0) -> None:
        """
        Stop publishes and complete bounded executor cleanup.
        Call this during application teardown.
        """
        self.request_stop()
        self.wait_for_stop(timeout)

    def request_stop(self) -> None:
        """Stop accepting work and request cancellation without waiting."""
        logger.info("Shutting down EventBus")
        with self._sub_lock:
            if not self._accepting_publishes:
                return
            self._accepting_publishes = False
            futures = tuple(self._futures)
            self._subscriptions.clear()
        for future in futures:
            future.cancel()
        self._executor.shutdown(wait=False, cancel_futures=True)

    def wait_for_stop(self, timeout: float) -> bool:
        """Wait up to ``timeout`` seconds for in-flight callbacks."""
        with self._sub_lock:
            futures = tuple(self._futures)
        if not futures:
            return True
        _done, pending = wait(futures, timeout=max(0.0, timeout))
        return not pending

    def _reinit_executor(self) -> None:
        """
        Explicitly reinitialize runtime state. Used for testing only.
        """
        with self._sub_lock:
            if self._accepting_publishes:
                return
            self._executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="EventBus")
            self._futures.clear()
            self._subscriptions.clear()
            self._accepting_publishes = True
