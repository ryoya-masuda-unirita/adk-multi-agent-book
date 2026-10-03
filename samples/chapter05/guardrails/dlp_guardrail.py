# 5-4-5. 発展: DLP（Data Loss Prevention）統合
# 実行には boto3 パッケージと BEDROCK_GUARDRAIL_ID 環境変数が必要
"""Amazon Bedrock Guardrailsを活用したガードレール"""
import os
from typing import Optional

import boto3
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_response import LlmResponse
from google.genai import types


def create_pii_guardrail(name: str = "agent-pii-guardrail") -> str:
    """個人情報を検出してマスキングするガードレールを作成し、IDを返す

    セットアップ時に1回だけ実行する。作成されたIDを環境変数
    BEDROCK_GUARDRAIL_ID に設定して DlpGuardrail から利用する。
    """
    client = boto3.client("bedrock")
    response = client.create_guardrail(
        name=name,
        description="エージェントの出力に含まれる個人情報をマスキングする",
        blockedInputMessaging="この入力は処理できません。",
        blockedOutputsMessaging="この応答は表示できません。",
        sensitiveInformationPolicyConfig={
            # 組み込みの個人情報タイプ。ANONYMIZEは検出箇所を{PHONE}のような表記に置き換える
            "piiEntitiesConfig": [
                {"type": "PHONE", "action": "ANONYMIZE"},
                {"type": "EMAIL", "action": "ANONYMIZE"},
                {"type": "CREDIT_DEBIT_CARD_NUMBER", "action": "ANONYMIZE"},
            ],
            # 組み込みに無い日本固有の情報は、正規表現で定義する
            "regexesConfig": [
                {
                    "name": "JAPAN_MY_NUMBER",
                    "description": "マイナンバー（12桁の数字）",
                    # Guardrailsの正規表現は先読み・後読みを使えないため、単純な形にする。
                    # 16桁のカード番号の一部にも一致するが、どちらもマスキング対象なので問題ない
                    "pattern": r"\b\d{4}[- ]?\d{4}[- ]?\d{4}\b",
                    "action": "ANONYMIZE",
                },
                {
                    "name": "JAPAN_PASSPORT",
                    "description": "日本の旅券番号（英字2文字と数字7桁）",
                    "pattern": r"\b[A-Z]{2}\d{7}\b",
                    "action": "ANONYMIZE",
                },
            ],
        },
    )
    return response["guardrailId"]


class DlpGuardrail:
    """Bedrock Guardrailsを使用した個人情報保護ガードレール"""

    def __init__(self):
        self.client = boto3.client("bedrock-runtime")
        self.guardrail_id = os.environ["BEDROCK_GUARDRAIL_ID"]
        # DRAFTは編集中の最新版。本番では発行済みのバージョン番号を指定する
        self.guardrail_version = os.environ.get(
            "BEDROCK_GUARDRAIL_VERSION", "DRAFT"
        )

    def check_output(
        self,
        callback_context: CallbackContext,
        llm_response: LlmResponse,
    ) -> Optional[LlmResponse]:
        """LLM出力をBedrock Guardrailsで検査する"""
        response_text = self._extract_text(llm_response)
        if not response_text:
            return None

        # Guardrailsで検査し、個人情報が検出された場合はマスキング済みのテキストを受け取る
        masked_text = self._apply_guardrail(response_text)

        if masked_text is not None:
            return LlmResponse(
                content=types.Content(
                    parts=[types.Part(text=masked_text)],
                    role="model",
                )
            )

        return None

    def _apply_guardrail(self, text: str) -> Optional[str]:
        """Guardrailsでコンテンツを検査し、匿名化したテキストを返す

        個人情報が検出されなかった場合は None を返す。
        """
        response = self.client.apply_guardrail(
            guardrailIdentifier=self.guardrail_id,
            guardrailVersion=self.guardrail_version,
            source="OUTPUT",
            content=[{"text": {"text": text}}],
        )

        if response["action"] != "GUARDRAIL_INTERVENED":
            return None

        return response["outputs"][0]["text"]

    def _extract_text(
        self,
        response: LlmResponse,
    ) -> Optional[str]:
        """レスポンスからテキストを抽出する"""
        if not response.content or not response.content.parts:
            return None
        for part in response.content.parts:
            if part.text:
                return part.text
        return None
