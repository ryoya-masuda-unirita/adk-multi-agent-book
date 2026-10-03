import os
import boto3


def get_secret(secret_id: str, region_name: str | None = None) -> str:
    """AWS Secrets Managerから認証情報を取得する"""
    if region_name is None:
        # 未設定の場合はAWSプロファイルのregionが使われる
        region_name = os.environ.get("AWS_REGION")

    client = boto3.client("secretsmanager", region_name=region_name)
    response = client.get_secret_value(SecretId=secret_id)
    return response["SecretString"]


def create_authenticated_tool(api_name: str) -> dict:
    """認証情報をSecrets Managerから取得してツール設定を構成する"""
    api_key = get_secret(f"{api_name}-api-key")
    return {
        "api_key": api_key,
        "timeout": 30,
        "retry_count": 3,
    }
