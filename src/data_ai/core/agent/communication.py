"""
DATA-AI Agent 通信机制

提供多 Agent 之间的通信能力，包括消息传递、广播、订阅等。
参考 Hermes 和 Trae 的多 Agent 架构设计。
"""

from __future__ import annotations

import asyncio
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from ...utils.exceptions import AgentException
from ...utils.logging import get_logger

logger = get_logger(__name__)


class MessageType(Enum):
    """消息类型"""

    REQUEST = "request"  # 请求消息
    RESPONSE = "response"  # 响应消息
    NOTIFICATION = "notification"  # 通知消息
    BROADCAST = "broadcast"  # 广播消息
    COMMAND = "command"  # 命令消息
    QUERY = "query"  # 查询消息
    RESULT = "result"  # 结果消息
    ERROR = "error"  # 错误消息
    HEARTBEAT = "heartbeat"  # 心跳消息
    STATUS = "status"  # 状态消息


class MessagePriority(Enum):
    """消息优先级"""

    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


class MessageStatus(Enum):
    """消息状态"""

    PENDING = "pending"  # 待处理
    DELIVERED = "delivered"  # 已送达
    READ = "read"  # 已读
    PROCESSED = "processed"  # 已处理
    FAILED = "failed"  # 失败
    EXPIRED = "expired"  # 已过期


@dataclass
class Message:
    """
    消息类

    表示 Agent 之间传递的消息
    """

    message_id: str
    sender_id: str
    receiver_id: str | None = None  # None 表示广播
    message_type: MessageType = MessageType.NOTIFICATION
    priority: MessagePriority = MessagePriority.NORMAL
    content: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)
    correlation_id: str | None = None  # 关联消息ID（用于请求-响应模式）
    reply_to: str | None = None  # 回复地址
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: datetime | None = None
    status: MessageStatus = MessageStatus.PENDING
    delivered_at: datetime | None = None
    processed_at: datetime | None = None

    def __post_init__(self):
        """初始化后处理"""
        if not self.message_id:
            self.message_id = str(uuid.uuid4())

    @property
    def is_broadcast(self) -> bool:
        """是否为广播消息"""
        return self.receiver_id is None

    @property
    def is_expired(self) -> bool:
        """是否已过期"""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at

    @property
    def age_seconds(self) -> float:
        """消息年龄（秒）"""
        return (datetime.now() - self.created_at).total_seconds()

    def create_response(
        self,
        content: Any,
        message_type: MessageType = MessageType.RESPONSE,
    ) -> Message:
        """
        创建响应消息

        Args:
            content: 响应内容
            message_type: 消息类型

        Returns:
            响应消息
        """
        return Message(
            message_id=str(uuid.uuid4()),
            sender_id=self.receiver_id or "unknown",
            receiver_id=self.sender_id,
            message_type=message_type,
            content=content,
            correlation_id=self.message_id,
            reply_to=self.sender_id,
        )

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "message_id": self.message_id,
            "sender_id": self.sender_id,
            "receiver_id": self.receiver_id,
            "message_type": self.message_type.value,
            "priority": self.priority.value,
            "content": self.content
            if not isinstance(self.content, (dict, list, str, int, float, bool, type(None)))
            else self.content,
            "metadata": self.metadata,
            "correlation_id": self.correlation_id,
            "reply_to": self.reply_to,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "status": self.status.value,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Message:
        """从字典创建消息"""
        return cls(
            message_id=data.get("message_id", str(uuid.uuid4())),
            sender_id=data["sender_id"],
            receiver_id=data.get("receiver_id"),
            message_type=MessageType(data.get("message_type", "notification")),
            priority=MessagePriority(data.get("priority", 2)),
            content=data.get("content"),
            metadata=data.get("metadata", {}),
            correlation_id=data.get("correlation_id"),
            reply_to=data.get("reply_to"),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
            status=MessageStatus(data.get("status", "pending")),
        )


@dataclass
class MessageQueue:
    """
    消息队列

    为每个 Agent 维护消息队列
    """

    agent_id: str
    max_size: int = 1000
    messages: list[Message] = field(default_factory=list)

    def push(self, message: Message) -> bool:
        """
        添加消息到队列

        Args:
            message: 消息

        Returns:
            是否成功添加
        """
        if len(self.messages) >= self.max_size:
            # 移除最旧的消息
            self.messages.pop(0)

        self.messages.append(message)
        return True

    def pop(self) -> Message | None:
        """
        取出最早的消息

        Returns:
            消息，如果队列为空返回 None
        """
        if self.messages:
            return self.messages.pop(0)
        return None

    def peek(self) -> Message | None:
        """
        查看最早的消息但不移除

        Returns:
            消息，如果队列为空返回 None
        """
        if self.messages:
            return self.messages[0]
        return None

    def get_by_priority(self, priority: MessagePriority) -> list[Message]:
        """
        获取指定优先级的消息

        Args:
            priority: 优先级

        Returns:
            消息列表
        """
        return [m for m in self.messages if m.priority == priority]

    def get_by_type(self, message_type: MessageType) -> list[Message]:
        """
        获取指定类型的消息

        Args:
            message_type: 消息类型

        Returns:
            消息列表
        """
        return [m for m in self.messages if m.message_type == message_type]

    def remove_expired(self) -> int:
        """
        移除过期消息

        Returns:
            移除的消息数量
        """
        original_len = len(self.messages)
        self.messages = [m for m in self.messages if not m.is_expired]
        return original_len - len(self.messages)

    def clear(self) -> None:
        """清空队列"""
        self.messages.clear()

    @property
    def size(self) -> int:
        """队列大小"""
        return len(self.messages)

    @property
    def is_empty(self) -> bool:
        """是否为空"""
        return len(self.messages) == 0


class SubscriptionManager:
    """
    订阅管理器

    管理 Agent 之间的订阅关系
    """

    def __init__(self):
        """初始化订阅管理器"""
        # topic -> set of subscriber_ids
        self._subscriptions: dict[str, set[str]] = defaultdict(set)
        # subscriber_id -> set of topics
        self._subscriber_topics: dict[str, set[str]] = defaultdict(set)

        self.logger = get_logger(f"{__name__}.subscription")

    def subscribe(
        self,
        subscriber_id: str,
        topic: str,
    ) -> bool:
        """
        订阅主题

        Args:
            subscriber_id: 订阅者 ID
            topic: 主题

        Returns:
            是否成功订阅
        """
        self._subscriptions[topic].add(subscriber_id)
        self._subscriber_topics[subscriber_id].add(topic)

        self.logger.debug(
            "订阅成功",
            subscriber=subscriber_id,
            topic=topic,
        )

        return True

    def unsubscribe(
        self,
        subscriber_id: str,
        topic: str | None = None,
    ) -> int:
        """
        取消订阅

        Args:
            subscriber_id: 订阅者 ID
            topic: 主题，None 表示取消所有订阅

        Returns:
            取消的订阅数量
        """
        count = 0

        if topic:
            if subscriber_id in self._subscriptions.get(topic, set()):
                self._subscriptions[topic].discard(subscriber_id)
                self._subscriber_topics[subscriber_id].discard(topic)
                count = 1
        else:
            # 取消所有订阅
            topics = self._subscriber_topics.get(subscriber_id, set()).copy()
            for t in topics:
                self._subscriptions[t].discard(subscriber_id)
                count += 1
            self._subscriber_topics[subscriber_id].clear()

        self.logger.debug(
            "取消订阅",
            subscriber=subscriber_id,
            topic=topic,
            count=count,
        )

        return count

    def get_subscribers(self, topic: str) -> set[str]:
        """
        获取主题的订阅者

        Args:
            topic: 主题

        Returns:
            订阅者 ID 集合
        """
        return self._subscriptions.get(topic, set()).copy()

    def get_subscriptions(self, subscriber_id: str) -> set[str]:
        """
        获取订阅者的所有订阅

        Args:
            subscriber_id: 订阅者 ID

        Returns:
            主题集合
        """
        return self._subscriber_topics.get(subscriber_id, set()).copy()

    def is_subscribed(self, subscriber_id: str, topic: str) -> bool:
        """
        检查是否已订阅

        Args:
            subscriber_id: 订阅者 ID
            topic: 主题

        Returns:
            是否已订阅
        """
        return subscriber_id in self._subscriptions.get(topic, set())

    def get_all_topics(self) -> set[str]:
        """获取所有主题"""
        return set(self._subscriptions.keys())

    def get_all_subscribers(self) -> set[str]:
        """获取所有订阅者"""
        return set(self._subscriber_topics.keys())

    def clear(self) -> None:
        """清空所有订阅"""
        self._subscriptions.clear()
        self._subscriber_topics.clear()


class BaseChannel(ABC):
    """
    通道基类

    定义 Agent 之间通信的通道抽象
    """

    @abstractmethod
    async def send(self, message: Message) -> bool:
        """
        发送消息

        Args:
            message: 消息

        Returns:
            是否成功发送
        """
        pass

    @abstractmethod
    async def receive(
        self,
        receiver_id: str,
        timeout: float | None = None,
    ) -> Message | None:
        """
        接收消息

        Args:
            receiver_id: 接收者 ID
            timeout: 超时时间（秒）

        Returns:
            消息，如果没有返回 None
        """
        pass

    @abstractmethod
    def get_pending_messages(self, receiver_id: str) -> list[Message]:
        """
        获取待处理消息

        Args:
            receiver_id: 接收者 ID

        Returns:
            待处理消息列表
        """
        pass


class DirectChannel(BaseChannel):
    """
    直接通道

    用于两个 Agent 之间的直接通信
    """

    def __init__(
        self,
        channel_id: str | None = None,
        max_queue_size: int = 100,
    ):
        """
        初始化直接通道

        Args:
            channel_id: 通道 ID
            max_queue_size: 最大队列大小
        """
        self.channel_id = channel_id or str(uuid.uuid4())
        self.max_queue_size = max_queue_size

        # agent_id -> message queue
        self._queues: dict[str, MessageQueue] = {}
        # 等待接收的事件
        self._wait_events: dict[str, asyncio.Event] = {}

        self.logger = get_logger(f"{__name__}.direct.{self.channel_id[:8]}")

    def _get_or_create_queue(self, agent_id: str) -> MessageQueue:
        """获取或创建消息队列"""
        if agent_id not in self._queues:
            self._queues[agent_id] = MessageQueue(
                agent_id=agent_id,
                max_size=self.max_queue_size,
            )
        return self._queues[agent_id]

    async def send(self, message: Message) -> bool:
        """
        发送消息

        Args:
            message: 消息

        Returns:
            是否成功发送
        """
        if message.is_broadcast:
            self.logger.warning("直接通道不支持广播消息")
            return False

        if message.is_expired:
            self.logger.debug("消息已过期，跳过发送")
            return False

        receiver_id = message.receiver_id
        queue = self._get_or_create_queue(receiver_id)

        success = queue.push(message)

        if success:
            message.status = MessageStatus.DELIVERED
            message.delivered_at = datetime.now()

            # 触发等待事件
            if receiver_id in self._wait_events:
                self._wait_events[receiver_id].set()

            self.logger.debug(
                "消息已发送",
                message_id=message.message_id,
                sender=message.sender_id,
                receiver=receiver_id,
            )

        return success

    async def receive(
        self,
        receiver_id: str,
        timeout: float | None = None,
    ) -> Message | None:
        """
        接收消息

        Args:
            receiver_id: 接收者 ID
            timeout: 超时时间（秒）

        Returns:
            消息，如果没有返回 None
        """
        queue = self._queues.get(receiver_id)

        if not queue or queue.is_empty:
            # 等待消息到达
            if timeout is not None and timeout > 0:
                event = asyncio.Event()
                self._wait_events[receiver_id] = event

                try:
                    await asyncio.wait_for(event.wait(), timeout=timeout)
                except asyncio.TimeoutError:
                    return None
                finally:
                    del self._wait_events[receiver_id]

        queue = self._queues.get(receiver_id)
        if not queue:
            return None

        message = queue.pop()

        if message:
            message.status = MessageStatus.READ
            self.logger.debug(
                "消息已接收",
                message_id=message.message_id,
                receiver=receiver_id,
            )

        return message

    def get_pending_messages(self, receiver_id: str) -> list[Message]:
        """获取待处理消息"""
        queue = self._queues.get(receiver_id)
        if queue:
            return queue.messages.copy()
        return []

    def clear_queue(self, agent_id: str) -> int:
        """
        清空指定 Agent 的消息队列

        Args:
            agent_id: Agent ID

        Returns:
            清空的消息数量
        """
        queue = self._queues.get(agent_id)
        if queue:
            count = queue.size
            queue.clear()
            return count
        return 0


class BroadcastChannel(BaseChannel):
    """
    广播通道

    用于向多个 Agent 广播消息
    """

    def __init__(
        self,
        channel_id: str | None = None,
        subscription_manager: SubscriptionManager | None = None,
    ):
        """
        初始化广播通道

        Args:
            channel_id: 通道 ID
            subscription_manager: 订阅管理器
        """
        self.channel_id = channel_id or str(uuid.uuid4())
        self.subscription_manager = subscription_manager or SubscriptionManager()

        # topic -> message history
        self._history: dict[str, list[Message]] = defaultdict(list)
        self._max_history_per_topic = 100

        self.logger = get_logger(f"{__name__}.broadcast.{self.channel_id[:8]}")

    async def send(self, message: Message) -> bool:
        """
        发送广播消息

        Args:
            message: 消息

        Returns:
            是否成功发送
        """
        if not message.is_broadcast:
            self.logger.warning("广播通道只支持广播消息")
            return False

        if message.is_expired:
            self.logger.debug("消息已过期，跳过发送")
            return False

        # 获取主题（从 metadata 中）
        topic = message.metadata.get("topic", "default")

        # 保存到历史记录
        self._history[topic].append(message)
        if len(self._history[topic]) > self._max_history_per_topic:
            self._history[topic].pop(0)

        message.status = MessageStatus.DELIVERED
        message.delivered_at = datetime.now()

        self.logger.debug(
            "广播消息已发送",
            message_id=message.message_id,
            sender=message.sender_id,
            topic=topic,
            subscribers=len(self.subscription_manager.get_subscribers(topic)),
        )

        return True

    async def receive(
        self,
        receiver_id: str,
        timeout: float | None = None,
    ) -> Message | None:
        """
        接收消息（广播通道不支持直接接收）

        广播通道需要通过订阅机制接收消息
        """
        self.logger.warning("广播通道不支持直接接收，请使用订阅机制")
        return None

    def get_pending_messages(self, receiver_id: str) -> list[Message]:
        """获取待处理消息"""
        messages: list[Message] = []

        # 获取订阅者的所有订阅主题
        subscriptions = self.subscription_manager.get_subscriptions(receiver_id)

        for topic in subscriptions:
            # 获取该主题的历史消息
            history = self._history.get(topic, [])
            for msg in history:
                # 检查消息是否已处理
                processed_key = f"processed_{receiver_id}"
                if not msg.metadata.get(processed_key):
                    messages.append(msg)

        # 按时间排序
        messages.sort(key=lambda m: m.created_at)

        return messages

    def mark_processed(self, message: Message, receiver_id: str) -> None:
        """
        标记消息已处理

        Args:
            message: 消息
            receiver_id: 接收者 ID
        """
        processed_key = f"processed_{receiver_id}"
        message.metadata[processed_key] = True
        message.status = MessageStatus.PROCESSED
        message.processed_at = datetime.now()

    def get_history(self, topic: str, limit: int = 10) -> list[Message]:
        """
        获取主题历史消息

        Args:
            topic: 主题
            limit: 最大数量

        Returns:
            历史消息列表
        """
        history = self._history.get(topic, [])
        return history[-limit:]

    def clear_history(self, topic: str | None = None) -> int:
        """
        清空历史记录

        Args:
            topic: 主题，None 表示清空所有

        Returns:
            清空的消息数量
        """
        count = 0

        if topic:
            count = len(self._history.get(topic, []))
            self._history[topic] = []
        else:
            for t in self._history:
                count += len(self._history[t])
            self._history.clear()

        return count


class MessageBus:
    """
    消息总线

    统一管理所有 Agent 之间的通信，提供消息路由、
    队列管理、订阅发布等功能。
    """

    def __init__(
        self,
        bus_id: str | None = None,
        max_queue_size: int = 1000,
        enable_broadcast: bool = True,
    ):
        """
        初始化消息总线

        Args:
            bus_id: 总线 ID
            max_queue_size: 最大队列大小
            enable_broadcast: 是否启用广播
        """
        self.bus_id = bus_id or str(uuid.uuid4())
        self.max_queue_size = max_queue_size
        self.enable_broadcast = enable_broadcast

        # 直接通道
        self._direct_channel = DirectChannel(
            max_queue_size=max_queue_size,
        )

        # 广播通道
        self._broadcast_channel: BroadcastChannel | None = None
        if enable_broadcast:
            self._broadcast_channel = BroadcastChannel()

        # 消息处理器
        # message_type -> list of handlers
        self._handlers: dict[MessageType, list[Callable[[Message], Awaitable[None]]]] = defaultdict(list)

        # 统计信息
        self._stats = {
            "total_sent": 0,
            "total_delivered": 0,
            "total_failed": 0,
            "by_type": defaultdict(int),
        }

        self._running = False
        self._processor_task: asyncio.Task | None = None

        self.logger = get_logger(f"{__name__}.bus.{self.bus_id[:8]}")

    async def start(self) -> None:
        """启动消息总线"""
        if self._running:
            return

        self._running = True
        self.logger.info("消息总线已启动", bus_id=self.bus_id)

    async def stop(self) -> None:
        """停止消息总线"""
        self._running = False

        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass

        self.logger.info("消息总线已停止", bus_id=self.bus_id)

    async def send(
        self,
        message: Message,
        channel: str = "direct",
    ) -> bool:
        """
        发送消息

        Args:
            message: 消息
            channel: 通道类型 (direct, broadcast)

        Returns:
            是否成功发送
        """
        self._stats["total_sent"] += 1
        self._stats["by_type"][message.message_type] += 1

        if channel == "broadcast" and self._broadcast_channel:
            success = await self._broadcast_channel.send(message)
        else:
            success = await self._direct_channel.send(message)

        if success:
            self._stats["total_delivered"] += 1
        else:
            self._stats["total_failed"] += 1

        return success

    async def send_direct(
        self,
        sender_id: str,
        receiver_id: str,
        content: Any,
        message_type: MessageType = MessageType.NOTIFICATION,
        priority: MessagePriority = MessagePriority.NORMAL,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """
        发送直接消息

        Args:
            sender_id: 发送者 ID
            receiver_id: 接收者 ID
            content: 消息内容
            message_type: 消息类型
            priority: 优先级
            metadata: 元数据

        Returns:
            是否成功发送
        """
        message = Message(
            message_id=str(uuid.uuid4()),
            sender_id=sender_id,
            receiver_id=receiver_id,
            message_type=message_type,
            priority=priority,
            content=content,
            metadata=metadata or {},
        )

        return await self.send(message, channel="direct")

    async def broadcast(
        self,
        sender_id: str,
        content: Any,
        topic: str = "default",
        message_type: MessageType = MessageType.BROADCAST,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """
        广播消息

        Args:
            sender_id: 发送者 ID
            content: 消息内容
            topic: 主题
            message_type: 消息类型
            metadata: 元数据

        Returns:
            是否成功发送
        """
        if not self._broadcast_channel:
            self.logger.warning("广播通道未启用")
            return False

        msg_metadata = metadata or {}
        msg_metadata["topic"] = topic

        message = Message(
            message_id=str(uuid.uuid4()),
            sender_id=sender_id,
            receiver_id=None,  # 广播
            message_type=message_type,
            content=content,
            metadata=msg_metadata,
        )

        return await self.send(message, channel="broadcast")

    async def receive(
        self,
        receiver_id: str,
        timeout: float | None = None,
        include_broadcast: bool = True,
    ) -> Message | None:
        """
        接收消息

        Args:
            receiver_id: 接收者 ID
            timeout: 超时时间（秒）
            include_broadcast: 是否包含广播消息

        Returns:
            消息
        """
        # 先尝试直接消息
        message = await self._direct_channel.receive(receiver_id, timeout=0)

        if message:
            return message

        # 再尝试广播消息
        if include_broadcast and self._broadcast_channel:
            broadcast_messages = self._broadcast_channel.get_pending_messages(receiver_id)
            if broadcast_messages:
                message = broadcast_messages[0]
                self._broadcast_channel.mark_processed(message, receiver_id)
                return message

        # 如果没有消息且设置了超时，等待
        if timeout and timeout > 0:
            await asyncio.sleep(min(timeout, 0.1))
            return await self.receive(receiver_id, timeout=None, include_broadcast=include_broadcast)

        return None

    def subscribe(
        self,
        subscriber_id: str,
        topic: str,
    ) -> bool:
        """
        订阅主题

        Args:
            subscriber_id: 订阅者 ID
            topic: 主题

        Returns:
            是否成功订阅
        """
        if self._broadcast_channel:
            return self._broadcast_channel.subscription_manager.subscribe(subscriber_id, topic)
        return False

    def unsubscribe(
        self,
        subscriber_id: str,
        topic: str | None = None,
    ) -> int:
        """
        取消订阅

        Args:
            subscriber_id: 订阅者 ID
            topic: 主题

        Returns:
            取消的订阅数量
        """
        if self._broadcast_channel:
            return self._broadcast_channel.subscription_manager.unsubscribe(subscriber_id, topic)
        return 0

    def register_handler(
        self,
        message_type: MessageType,
        handler: Callable[[Message], Awaitable[None]],
    ) -> None:
        """
        注册消息处理器

        Args:
            message_type: 消息类型
            handler: 处理器函数
        """
        self._handlers[message_type].append(handler)
        self.logger.debug(
            "消息处理器已注册",
            message_type=message_type.value,
        )

    def unregister_handler(
        self,
        message_type: MessageType,
        handler: Callable[[Message], Awaitable[None]],
    ) -> bool:
        """
        注销消息处理器

        Args:
            message_type: 消息类型
            handler: 处理器函数

        Returns:
            是否成功注销
        """
        if handler in self._handlers[message_type]:
            self._handlers[message_type].remove(handler)
            return True
        return False

    async def process_message(self, message: Message) -> None:
        """
        处理消息

        Args:
            message: 消息
        """
        handlers = self._handlers.get(message.message_type, [])

        for handler in handlers:
            try:
                await handler(message)
            except Exception as e:
                self.logger.error(
                    "消息处理器执行失败",
                    message_id=message.message_id,
                    error=str(e),
                )

    def get_pending_messages(self, agent_id: str) -> list[Message]:
        """
        获取 Agent 的所有待处理消息

        Args:
            agent_id: Agent ID

        Returns:
            待处理消息列表
        """
        messages = self._direct_channel.get_pending_messages(agent_id)

        if self._broadcast_channel:
            messages.extend(self._broadcast_channel.get_pending_messages(agent_id))

        # 按优先级排序
        messages.sort(key=lambda m: m.priority.value, reverse=True)

        return messages

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        return {
            "bus_id": self.bus_id,
            "running": self._running,
            "total_sent": self._stats["total_sent"],
            "total_delivered": self._stats["total_delivered"],
            "total_failed": self._stats["total_failed"],
            "by_type": dict(self._stats["by_type"]),
        }

    def clear(self) -> None:
        """清空消息总线"""
        self._direct_channel._queues.clear()
        if self._broadcast_channel:
            self._broadcast_channel.clear_history()
        self._stats = {
            "total_sent": 0,
            "total_delivered": 0,
            "total_failed": 0,
            "by_type": defaultdict(int),
        }


class CommunicationError(AgentException):
    """通信错误"""

    def __init__(
        self,
        message: str,
        message_id: str | None = None,
        sender_id: str | None = None,
        receiver_id: str | None = None,
        cause: Exception | None = None,
    ):
        super().__init__(message, cause=cause)
        self.message_id = message_id
        self.sender_id = sender_id
        self.receiver_id = receiver_id
