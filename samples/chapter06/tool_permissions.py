# samples/chapter06/tool_permissions.py
"""エージェントごとのツール権限マトリクス"""

# エージェントのロール定義
AGENT_ROLES = {
    "data_analyst": {
        "allowed_tools": ["athena"],
        "denied_tools": ["rds", "aws", "kubectl"],
        "max_risk_level": "medium",
    },
    "sre_operator": {
        "allowed_tools": ["aws", "kubectl", "athena"],
        "denied_tools": [],
        "max_risk_level": "high",
    },
    "db_administrator": {
        "allowed_tools": ["rds", "athena"],
        "denied_tools": ["aws", "kubectl"],
        "max_risk_level": "high",
    },
}
