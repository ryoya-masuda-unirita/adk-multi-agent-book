# samples/chapter08/deploy/app_runner/agent.py
"""App Runnerデプロイ用のエージェント定義

app.pyが `from agent import root_agent` で読み込む最小構成のエージェント。
実際のデプロイでは、samples/chapter08/support_agent/ のエージェント定義を
このディレクトリに配置して差し替える。
"""
from google.adk import Agent

root_agent = Agent(
    name="support_agent",
    model="bedrock/global.anthropic.claude-sonnet-5-5",
    instruction="""あなたはカスタマーサポートエージェントです。
ユーザーの問い合わせに簡潔に回答してください。
事実のみを回答し、推測は行わないでください。""",
)
