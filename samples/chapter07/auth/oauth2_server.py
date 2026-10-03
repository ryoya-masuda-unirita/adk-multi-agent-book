# samples/chapter07/auth/oauth2_server.py
"""OAuth2トークン検証ミドルウェア付きA2Aサーバー（7-5-2 サーバー側）

Starlette のミドルウェアとしてトークン検証を差し込み、to_a2a() が返す
Starlette アプリに add_middleware で登録する。Agent Card エンドポイント
（/.well-known/）は認証不要とし、それ以外は Bearer トークンの検証と
スコープ（expense:read / expense:write）の確認を行う。

環境変数:
    COGNITO_USER_POOL_ID: トークンを発行するAmazon CognitoユーザープールのID（必須）
    COGNITO_CLIENT_ID: 呼び出しを許可するアプリクライアントのID（必須）
    AWS_REGION: ユーザープールのリージョン（デフォルト: ap-northeast-1）
"""

import os

import jwt
import uvicorn
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from a2a.types import AgentCard
from google.adk import Agent
from google.adk.a2a.utils.agent_to_a2a import to_a2a


def verify_token(token: str) -> dict | None:
    """OAuth2トークンを検証する"""
    try:
        # Amazon Cognito を使用する場合
        region = os.environ.get("AWS_REGION", "ap-northeast-1")
        issuer = (
            f"https://cognito-idp.{region}.amazonaws.com/"
            f"{os.environ['COGNITO_USER_POOL_ID']}"
        )
        # ユーザープールが公開している鍵で、トークンの署名・発行元・有効期限を検証する
        signing_key = jwt.PyJWKClient(
            f"{issuer}/.well-known/jwks.json"
        ).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=issuer,
        )
        # Cognitoのアクセストークンはaudienceを持たないため、client_idで呼び出し元を確認する
        if claims.get("token_use") != "access":
            return None
        if claims.get("client_id") != os.environ["COGNITO_CLIENT_ID"]:
            return None
        return claims
    except jwt.PyJWTError:
        return None


class OAuth2Middleware(BaseHTTPMiddleware):
    """Bearer トークンを検証する認証ミドルウェア"""

    async def dispatch(self, request, call_next):
        # Agent Card エンドポイントは認証不要
        if request.url.path.startswith("/.well-known/"):
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse({"error": "Missing or invalid Authorization header"}, status_code=401)

        token = auth_header[7:]
        claims = verify_token(token)
        if claims is None:
            return JSONResponse({"error": "Invalid token"}, status_code=401)

        # 必要なスコープの確認
        required_scopes = {"expense:read", "expense:write"}
        # Cognitoのスコープは「リソースサーバーの識別子/スコープ名」の形式のため、スコープ名だけを取り出す
        token_scopes = {
            scope.split("/")[-1] for scope in claims.get("scope", "").split()
        }
        if not required_scopes.issubset(token_scopes):
            return JSONResponse({"error": "Insufficient scope"}, status_code=403)

        return await call_next(request)


# ----- 以下はサーバーを単体実行するための補完コード -----

# 認証付きで公開する経費精算エージェント（最小構成）
expense_agent = Agent(
    name="secure_expense_agent",
    model="bedrock/global.anthropic.claude-sonnet-5-5",
    instruction="あなたは経費精算の専門エージェントです。経費の登録と照会の依頼に応答してください。",
)

# Agent Card: security_schemes でOAuth2（clientCredentialsフロー）の認証要件を宣言する
# クライアント側（oauth2_client.py）の scheme_name はこの "oauth2" と一致させる
agent_card = AgentCard.model_validate(
    {
        "name": "secure-expense-agent",
        "description": "認証付き経費精算エージェント",
        "url": "http://localhost:8001",
        "version": "1.0.0",
        "protocol_version": "0.3.0",
        "preferred_transport": "JSONRPC",
        "security_schemes": {
            "oauth2": {
                "type": "oauth2",
                "flows": {
                    "clientCredentials": {
                        "tokenUrl": "https://auth.example.com/oauth/token",
                        "scopes": {
                            "expense:read": "経費の読み取り",
                            "expense:write": "経費の書き込み",
                        },
                    }
                },
            }
        },
        "security": [{"oauth2": ["expense:read", "expense:write"]}],
        "capabilities": {"streaming": True},
        "skills": [
            {
                "id": "register-expense",
                "name": "経費登録",
                "description": "経費情報をシステムに登録する",
                "tags": ["expense", "registration"],
            }
        ],
        "default_input_modes": ["text"],
        "default_output_modes": ["text"],
    }
)

# 認証ミドルウェアを適用したA2Aサーバー
app = to_a2a(expense_agent, host="0.0.0.0", port=8001, agent_card=agent_card)
app.add_middleware(OAuth2Middleware)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
