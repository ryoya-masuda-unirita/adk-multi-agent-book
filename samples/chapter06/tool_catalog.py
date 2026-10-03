# samples/chapter06/tool_catalog.py
"""ツールカタログの定義例"""

TOOL_CATALOG = {
    "athena": {
        "type": "mcp",
        "package": "awslabs.aws-dataprocessing-mcp-server",
        "description": "Athenaへのクエリ実行・スキーマ参照",
        "required_iam_roles": ["AmazonAthenaFullAccess"],
        "risk_level": "medium",  # データ参照可能
        "approval_required": False,
    },
    "rds": {
        "type": "mcp",
        "package": "@toolbox-sdk/server",
        "config": "tools-rds.yaml",
        "description": "Amazon RDS（PostgreSQL/MySQL）への接続",
        "required_iam_roles": ["AmazonRDSReadOnlyAccess"],
        "risk_level": "high",  # 本番DBへのアクセス
        "approval_required": True,
    },
    "gcloud": {
        "type": "cli",
        "command": "gcloud",
        "description": "Google Cloudリソースの管理",
        "required_permissions": ["gcloud CLI認証済み"],
        "risk_level": "high",
        "approval_required": True,
    },
    "kubectl": {
        "type": "cli",
        "command": "kubectl",
        "description": "Kubernetesクラスタの操作",
        "required_permissions": ["kubeconfig設定済み"],
        "risk_level": "high",
        "approval_required": True,
    },
}
