# samples/chapter04/memory_agent/agentcore_memory.py
"""Amazon Bedrock AgentCore MemoryをADKのMemoryServiceとして使うための部品

ADKにはAgentCore Memory用のMemoryServiceが用意されていないため、
BaseMemoryServiceを継承して、対話の保存と記憶の検索を実装する。

AgentCore Memoryは、保存された対話から事実や嗜好を自動で抽出して長期記憶にする。
抽出は非同期で行われるため、保存した直後の対話は検索結果にまだ現れない。
"""
import asyncio
from datetime import datetime, timezone

import boto3
from google.adk.memory import BaseMemoryService
from google.adk.memory.base_memory_service import SearchMemoryResponse
from google.adk.memory.memory_entry import MemoryEntry
from google.adk.sessions import Session
from google.genai import types


class AgentCoreMemoryService(BaseMemoryService):
    """AgentCore Memoryに対話を保存し、長期記憶を検索するMemoryService"""

    def __init__(
        self,
        memory_id: str,
        namespace_template: str = "/users/{actorId}",
        top_k: int = 5,
        region_name: str | None = None,
    ):
        """
        Args:
            memory_id: AgentCore MemoryのID
            namespace_template: 長期記憶の保存先。Memoryの戦略に設定したnamespaceと合わせる
            top_k: 検索で取得する記憶の最大件数
            region_name: Memoryのリージョン（省略時はAWSプロファイルの設定）
        """
        self._memory_id = memory_id
        self._namespace_template = namespace_template
        self._top_k = top_k
        self._client = boto3.client("bedrock-agentcore", region_name=region_name)
        # 送信済みのイベントID。同じSessionを繰り返し保存しても重複して送らないために使う
        self._sent_event_ids: set[str] = set()

    async def add_session_to_memory(self, session: Session) -> None:
        """Sessionの対話のうち、未送信の発言をAgentCore Memoryへ保存する"""
        new_events = []
        payload = []
        for event in session.events:
            if event.id in self._sent_event_ids or not event.content:
                continue
            text = "".join(
                part.text for part in (event.content.parts or []) if part.text
            )
            if not text:
                continue
            new_events.append(event)
            payload.append({
                "conversational": {
                    "content": {"text": text},
                    "role": "USER" if event.author == "user" else "ASSISTANT",
                }
            })

        if not payload:
            return

        # boto3は同期APIのため、イベントループを止めないよう別スレッドで呼び出す
        await asyncio.to_thread(
            self._client.create_event,
            memoryId=self._memory_id,
            actorId=session.user_id,
            sessionId=session.id,
            eventTimestamp=datetime.fromtimestamp(
                new_events[0].timestamp, tz=timezone.utc
            ),
            payload=payload,
        )
        self._sent_event_ids.update(event.id for event in new_events)

    async def search_memory(
        self,
        *,
        app_name: str,
        user_id: str,
        query: str,
    ) -> SearchMemoryResponse:
        """ユーザーの長期記憶から、クエリに関連するものを検索する"""
        response = await asyncio.to_thread(
            self._client.retrieve_memory_records,
            memoryId=self._memory_id,
            namespace=self._namespace_template.format(actorId=user_id),
            searchCriteria={"searchQuery": query, "topK": self._top_k},
        )
        memories = [
            MemoryEntry(
                content=types.Content(
                    role="user",
                    parts=[types.Part(text=record["content"]["text"])],
                ),
                author="user",
                timestamp=record["createdAt"].isoformat(),
            )
            for record in response.get("memoryRecordSummaries", [])
        ]
        return SearchMemoryResponse(memories=memories)
