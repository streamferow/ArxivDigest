import json
import asyncio
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta


@dataclass
class UserSubscription:
    chat_id: int
    topics: List[str]
    interval_days: int
    next_digest_at: str
    last_digest_at: str 


class SubscriptionStorage:
    def __init__(self, path_to_storage: str = "telegram/data/subscriptions.json"):
        self.path_to_storage = Path(path_to_storage)
        self._lock = asyncio.Lock()


    async def _read_all(self) -> Dict[str, Dict]:
        raw_data = self.path_to_storage.read_text(encoding="utf-8").strip()
        if not raw_data:
            return {}
        return json.loads(raw_data)


    async def _write_all(self, payload: Dict[str, Dict]) -> None:
        self.path_to_storage.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), 
            encoding="utf-8"
        )


    async def get_user(self, chat_id: int) -> Optional[UserSubscription]:
        async with self._lock:
            data = await self._read_all()
            item = data.get(str(chat_id))
            if not item:
                return None
            return UserSubscription(**item)


    async def upsert_user_interval(self, chat_id: int, interval_days: int) -> UserSubscription:
        now = datetime.now(timezone.utc)
        next_digest_at = now + timedelta(days=interval_days)

        async with self._lock:
            data = await self._read_all()
            current = data.get(str(chat_id)) or {}
            topics = current.get("topics") or []

            subscription = UserSubscription(
                chat_id=chat_id,
                topics=topics,
                interval_days=interval_days,
                next_digest_at=next_digest_at.isoformat(),
                last_digest_at=current.get("last_digest_at") or now.isoformat(),
            )

            data[str(chat_id)] = asdict(subscription)
            await self._write_all(data)
            return subscription


    async def get_all_users(self) -> List[UserSubscription]:
        async with self._lock:
            data = await self._read_all()
            result: List[UserSubscription] = []
            for item in data.values():
                result.append(UserSubscription(**item))
            return result


    async def reschedule_next_digest(self, chat_id: int, interval_days: int) -> Optional[UserSubscription]:
        async with self._lock:
            data = await self._read_all()
            current = data.get(str(chat_id))
            if not current:
                return None

            sub = UserSubscription(**current)
            sub.interval_days = interval_days
            sub.next_digest_at = (datetime.now(timezone.utc) + timedelta(days=interval_days)).isoformat()

            data[str(chat_id)] = asdict(sub)
            await self._write_all(data)
            return sub


    async def mark_digest_sent(self, chat_id: int) -> Optional[UserSubscription]:
        async with self._lock:
            data = await self._read_all()
            current = data.get(str(chat_id))
            if not current:
                return None

            sub = UserSubscription(**current)
            sub.last_digest_at = datetime.now(timezone.utc).isoformat()

            data[str(chat_id)] = asdict(sub)
            await self._write_all(data)
            return sub


    async def set_user_topics(self, chat_id: int, topics: List[str]) -> UserSubscription:
      async with self._lock:
          data = await self._read_all()
          current = data.get(str(chat_id))
          if current:
              sub = UserSubscription(**current)
              sub.topics = topics
          else:
              default_days = 1
              now = datetime.now(timezone.utc)
              sub = UserSubscription(
                  chat_id=chat_id,
                  topics=topics,
                  interval_days=default_days,
                  next_digest_at=(now + timedelta(days=default_days)).isoformat(),
                  last_digest_at=None,
              )
          data[str(chat_id)] = asdict(sub)
          await self._write_all(data)
          return sub

