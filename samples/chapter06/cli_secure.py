# samples/chapter06/cli_secure.py
"""セキュリティを強化したCLIツール統合"""

import re
import shlex
import subprocess

from google.adk import Agent


# 許可するサブコマンドのホワイトリスト
# 値は、対象リソースを指定するときに使うオプション名（リソースを指定できないものはNone）
ALLOWED_AWS_SUBCOMMANDS = {
    "ec2 describe-instances": "--instance-ids",
    "apprunner list-services": None,
    "apprunner describe-service": "--service-arn",
    "rds describe-db-instances": "--db-instance-identifier",
    "eks list-clusters": None,
    "eks describe-cluster": "--name",
}


def safe_aws(subcommand: str, resource_name: str = "", flags: str = "") -> dict:
    """安全にAWS CLIコマンドを実行する

    Args:
        subcommand: 実行するサブコマンド（ホワイトリスト内のもの）
        resource_name: 対象リソースの名前・ID・ARN（英数字・ハイフン・アンダースコア・コロン・スラッシュのみ）
        flags: 追加フラグ（--region等）

    Returns:
        コマンドの実行結果"""
    # サブコマンドのホワイトリスト検証
    if subcommand not in ALLOWED_AWS_SUBCOMMANDS:
        return {"error": f"許可されていないサブコマンドです: {subcommand}"}

    # リソース名のバリデーション（英数字、ハイフン、アンダースコアと、ARNで使うコロン、スラッシュのみ）
    if resource_name and not re.match(r'^[a-zA-Z0-9_:/-]+$', resource_name):
        return {"error": "リソース名に不正な文字が含まれています"}

    resource_option = ALLOWED_AWS_SUBCOMMANDS[subcommand]
    if resource_name and resource_option is None:
        return {"error": f"このサブコマンドはリソースを指定できません: {subcommand}"}

    # フラグのバリデーション（--key=value形式のみ許可）
    safe_flags = []
    if flags:
        for flag in shlex.split(flags):
            if re.match(r'^--[a-z][a-z0-9-]*(=[\w./-]+)?$', flag):
                safe_flags.append(flag)
            else:
                return {"error": f"不正なフラグ形式です: {flag}"}

    # コマンドの組み立て（文字列結合ではなくリストで構築。shell=Trueは使わない）
    cmd = ["aws"] + subcommand.split()
    if resource_name:
        cmd.extend([resource_option, resource_name])
    cmd.extend(safe_flags)
    cmd.extend(["--output", "json"])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "return_code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"error": "コマンドがタイムアウトしました"}


# セキュリティ強化されたエージェント
secure_aws_agent = Agent(
    name="secure_aws_agent",
    model="bedrock/global.anthropic.claude-sonnet-5-5",
    instruction="""AWSリソースの参照を行うエージェントです。
    safe_awsツールでリソース情報を取得します。
    利用できるサブコマンドはホワイトリストで制限されています。""",
    tools=[safe_aws],
)
