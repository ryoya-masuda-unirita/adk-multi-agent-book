# samples/chapter08/deploy/deploy_sdk.py
"""Python SDK（boto3）を使ったAgentCore Runtimeデプロイ

CLIの代わりにPython SDKでデプロイする場合の例。
CI/CDパイプラインに組み込む場合に有用。

AgentCore Runtimeには、エージェントのコードと依存パッケージをzipにまとめて渡す。
実行環境はLinuxのARM64のため、依存パッケージはARM64向けのものを取得する
（取得には uv を使う）。

依存:
    boto3>=1.40.0
    uv（コマンド）

必要な環境変数:
    AGENTCORE_ROLE_ARN : AgentCore Runtimeの実行ロールのARN
    CODE_BUCKET        : zipを置くS3バケット名
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import boto3

# samples/chapter08（support_agent/ の親ディレクトリ）
CHAPTER_DIR = Path(__file__).resolve().parent.parent
AGENTCORE_DIR = Path(__file__).resolve().parent / "agentcore"

PYTHON_VERSION = "3.12"
AGENTCORE_PYTHON_RUNTIME = "PYTHON_3_12"


def build_package(output_dir: str) -> str:
    """エージェントのコードと依存パッケージをzipにまとめ、zipのパスを返す

    zipの中身は、main.py（エントリポイント）、support_agent/、依存パッケージ。
    """
    package_dir = Path(output_dir) / "package"

    # 依存パッケージをLinux ARM64向けに取得する（実行するPCのOSやCPUには依存しない）
    subprocess.run(
        [
            "uv", "pip", "install", "--quiet",
            "--python-platform", "aarch64-manylinux_2_28",
            "--python-version", PYTHON_VERSION,
            "--only-binary=:all:",
            "--target", str(package_dir),
            "-r", str(AGENTCORE_DIR / "requirements.txt"),
        ],
        check=True,
    )

    # エージェントのコードを配置する（.envや__pycache__は含めない）
    shutil.copy(AGENTCORE_DIR / "main.py", package_dir / "main.py")
    shutil.copytree(
        CHAPTER_DIR / "support_agent",
        package_dir / "support_agent",
        ignore=shutil.ignore_patterns(".env", "__pycache__"),
    )

    return shutil.make_archive(str(Path(output_dir) / "agent"), "zip", package_dir)


def _upload_package(display_name: str) -> dict:
    """zipをビルドしてS3へアップロードし、AgentCore Runtimeに渡すコード設定を返す"""
    bucket = os.environ.get("CODE_BUCKET")
    if not bucket:
        raise RuntimeError("環境変数 CODE_BUCKET を設定してください。")

    key = f"{display_name}/agent.zip"
    with tempfile.TemporaryDirectory() as work_dir:
        zip_path = build_package(work_dir)
        boto3.client("s3").upload_file(zip_path, bucket, key)

    return {
        "codeConfiguration": {
            "code": {"s3": {"bucket": bucket, "prefix": key}},
            "runtime": AGENTCORE_PYTHON_RUNTIME,
            "entryPoint": ["main.py"],
        }
    }


def _wait_until_ready(client, runtime_id: str) -> None:
    """ランタイムの作成・更新が完了するまで待つ"""
    while True:
        runtime = client.get_agent_runtime(agentRuntimeId=runtime_id)
        if runtime["status"] not in ("CREATING", "UPDATING"):
            break
        time.sleep(5)
    if runtime["status"] != "READY":
        raise RuntimeError(
            f"デプロイに失敗しました: {runtime['status']} "
            f"{runtime.get('failureReason', '')}"
        )


def deploy_agent(
    display_name: str,
    env_vars: dict[str, str] | None = None,
) -> str:
    """エージェントをAgentCore Runtimeにデプロイする

    実行ロールとzipの置き場所（S3バケット）は環境変数から解決する。

    Args:
        display_name: デプロイ名（英字で始まる英数字とアンダースコア。ハイフンは使えない）
        env_vars: ランタイムへ渡す環境変数

    Returns:
        デプロイされたランタイムのARN
    """
    role_arn = os.environ.get("AGENTCORE_ROLE_ARN")
    if not role_arn:
        raise RuntimeError("環境変数 AGENTCORE_ROLE_ARN を設定してください。")

    client = boto3.client("bedrock-agentcore-control")

    print(f"AgentCore Runtimeにデプロイ中: {display_name}")
    print(f"  Region:  {client.meta.region_name}")

    response = client.create_agent_runtime(
        agentRuntimeName=display_name,
        agentRuntimeArtifact=_upload_package(display_name),
        roleArn=role_arn,
        networkConfiguration={"networkMode": "PUBLIC"},
        protocolConfiguration={"serverProtocol": "HTTP"},
        environmentVariables=env_vars or {},
    )
    _wait_until_ready(client, response["agentRuntimeId"])

    runtime_arn = response["agentRuntimeArn"]
    print(f"\nデプロイ完了: {runtime_arn}")
    return runtime_arn


def update_agent(runtime_id: str) -> str:
    """デプロイ済みのエージェントを更新する

    Args:
        runtime_id: 更新対象のランタイムID

    Returns:
        更新されたランタイムのARN
    """
    client = boto3.client("bedrock-agentcore-control")
    current = client.get_agent_runtime(agentRuntimeId=runtime_id)

    print(f"AgentCore Runtimeを更新中: {runtime_id}")

    # 最新のエージェント実装でzipを作り直して既存のランタイムを更新する。
    # 更新すると新しいバージョンが作られ、既定のエンドポイントが新しいバージョンを指す
    response = client.update_agent_runtime(
        agentRuntimeId=runtime_id,
        agentRuntimeArtifact=_upload_package(current["agentRuntimeName"]),
        roleArn=current["roleArn"],
        networkConfiguration=current["networkConfiguration"],
        protocolConfiguration=current["protocolConfiguration"],
        environmentVariables=current.get("environmentVariables", {}),
    )
    _wait_until_ready(client, runtime_id)

    print(f"\n更新完了: {response['agentRuntimeArn']}")
    return response["agentRuntimeArn"]


def list_deployed_agents() -> list[dict]:
    """デプロイ済みのエージェント一覧を取得する

    Returns:
        デプロイ済みエージェントのリスト
    """
    client = boto3.client("bedrock-agentcore-control")

    results = []
    for runtime in client.list_agent_runtimes()["agentRuntimes"]:
        results.append({
            "name": runtime["agentRuntimeName"],
            "runtime_id": runtime["agentRuntimeId"],
            "runtime_arn": runtime["agentRuntimeArn"],
            "version": runtime["agentRuntimeVersion"],
            "status": runtime["status"],
            "update_time": str(runtime["lastUpdatedAt"]),
        })
    return results


def delete_agent(runtime_id: str) -> None:
    """デプロイ済みのエージェントを削除する

    Args:
        runtime_id: 削除対象のランタイムID
    """
    client = boto3.client("bedrock-agentcore-control")
    client.delete_agent_runtime(agentRuntimeId=runtime_id)
    print(f"削除完了: {runtime_id}")


if __name__ == "__main__":
    # デプロイ済みエージェントの一覧表示
    print("=== デプロイ済みエージェント ===")
    agents = list_deployed_agents()
    for agent in agents:
        print(f"  {agent['name']}: {agent['runtime_arn']}")

    if not agents:
        print("  （なし）")
        sys.exit(0)
