# samples/chapter06/cli_basic.py
"""CLIツールをADKエージェントのツールとして統合する基本パターン"""

import subprocess
import shlex

from google.adk import Agent


def run_aws_command(command: str) -> dict:
    """AWS CLIコマンドを実行する

    Args:
        command: 実行するawsサブコマンド（例: "ec2 describe-instances"）

    Returns:
        コマンドの実行結果（stdout, stderr, return_code）"""
    # コマンド文字列を安全に分割
    args = ["aws"] + shlex.split(command) + ["--output", "json"]

    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=30,  # 30秒でタイムアウト
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "return_code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {
            "stdout": "",
            "stderr": "コマンドがタイムアウトしました（30秒）",
            "return_code": -1,
        }


# AWS CLIツールを使うエージェント
aws_agent = Agent(
    name="aws_agent",
    model="bedrock/global.anthropic.claude-sonnet-5-5",
    instruction="""あなたはAWSリソースの管理を支援するエージェントです。

    awsコマンドを使ってリソースの参照・管理を行います。

    ## 使用可能なコマンド
    - ec2 describe-instances: EC2インスタンスの一覧
    - ec2 describe-instances --instance-ids INSTANCE_ID: EC2インスタンスの詳細
    - apprunner list-services: App Runnerサービスの一覧
    - rds describe-db-instances: RDSインスタンスの一覧
    - eks list-clusters: EKSクラスタの一覧

    ## 禁止事項
    - delete / terminate を含むコマンドは実行しない
    - IAMポリシーの変更は行わない
    - プロファイルやリージョンの設定変更は行わない""",
    tools=[run_aws_command],
)
