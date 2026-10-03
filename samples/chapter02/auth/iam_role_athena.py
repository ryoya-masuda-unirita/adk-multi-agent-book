# iam_role_athena.py
# 2-7-4. IAMロール認証（完全版）
# AWS環境では、ECSやLambdaなどに割り当てたIAMロールの認証情報が自動的に注入される。
# ローカル開発では、環境変数 AWS_PROFILE で指定したプロファイルの認証情報が使われる。
# 依存パッケージ: boto3

import os
import time

import boto3
from google.adk.tools import FunctionTool


def query_athena(
    sql: str,
) -> dict:
    """AthenaでSQLクエリを実行する。

    Args:
        sql: 実行するSQLクエリ

    Returns:
        クエリ結果"""
    # boto3の標準認証チェーンを使用
    # AWS環境では実行環境に割り当てたIAMロールが自動的に使用される
    client = boto3.client("athena")

    # クエリ結果の保存先（S3）は、ワークグループの設定を使う
    execution = client.start_query_execution(
        QueryString=sql,
        QueryExecutionContext={"Database": os.environ["ATHENA_DATABASE"]},
        WorkGroup=os.environ.get("ATHENA_WORKGROUP", "primary"),
    )
    execution_id = execution["QueryExecutionId"]

    # Athenaのクエリは非同期で実行されるため、完了まで状態を確認する
    while True:
        status = client.get_query_execution(
            QueryExecutionId=execution_id
        )["QueryExecution"]["Status"]
        if status["State"] not in ("QUEUED", "RUNNING"):
            break
        time.sleep(1)

    if status["State"] != "SUCCEEDED":
        return {
            "status": "error",
            "message": status.get("StateChangeReason", status["State"]),
        }

    # 1行目は列名のため、ヘッダーとして取り出す（最大100行を返す）
    result = client.get_query_results(
        QueryExecutionId=execution_id, MaxResults=101
    )
    header, *data_rows = [
        [column.get("VarCharValue") for column in row["Data"]]
        for row in result["ResultSet"]["Rows"]
    ]
    rows = [dict(zip(header, row)) for row in data_rows]
    return {"status": "success", "row_count": len(rows), "rows": rows}


athena_tool = FunctionTool(func=query_athena)

if __name__ == "__main__":
    # 定義の確認（実行には環境変数 ATHENA_DATABASE とAWSの認証設定が必要）
    print(f"ツール名: {athena_tool.name}")
