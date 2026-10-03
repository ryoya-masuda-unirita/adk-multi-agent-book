# samples/chapter06/tool_permissions.py
"""エージェントごとのツール権限マトリクス"""

# エージェントのロール定義
AGENT_ROLES = {
    "data_analyst": {
        "allowed_tools": ["bigquery"],
        "denied_tools": ["rds", "gcloud", "kubectl"],
        "max_risk_level": "medium",
    },
    "sre_operator": {
        "allowed_tools": ["gcloud", "kubectl", "bigquery"],
        "denied_tools": [],
        "max_risk_level": "high",
    },
    "db_administrator": {
        "allowed_tools": ["rds", "bigquery"],
        "denied_tools": ["gcloud", "kubectl"],
        "max_risk_level": "high",
    },
}
