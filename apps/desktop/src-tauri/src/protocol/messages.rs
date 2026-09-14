use serde::{Deserialize, Serialize};

pub const PROTOCOL_VERSION: &str = "1.0.0";

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "UPPERCASE")]
pub enum RiskLevel {
    Safe,
    Low,
    Medium,
    High,
    Critical,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UserMessagePayload {
    pub content: String,
    #[serde(default)]
    pub attachments: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolCallPayload {
    #[serde(rename = "taskId")]
    pub task_id: String,
    pub tool: String,
    #[serde(rename = "riskLevel")]
    pub risk_level: RiskLevel,
    #[serde(default)]
    pub arguments: serde_json::Value,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PermissionRequestPayload {
    #[serde(rename = "taskId")]
    pub task_id: String,
    #[serde(rename = "toolCallId")]
    pub tool_call_id: String,
    pub tool: String,
    #[serde(rename = "riskLevel")]
    pub risk_level: RiskLevel,
    pub description: String,
    #[serde(default)]
    pub arguments: serde_json::Value,
}
