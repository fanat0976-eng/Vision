"""Tool approval — controls which tools need user confirmation."""

import json
from pathlib import Path
from dataclasses import dataclass


@dataclass
class ApprovalRule:
    pattern: str
    action: str  # "allow", "ask", "deny"


class ApprovalManager:
    """Manages tool approval rules."""

    def __init__(self):
        self.rules: list[ApprovalRule] = []
        self._load_defaults()

    def _load_defaults(self):
        self.rules = [
            ApprovalRule(pattern="read_file", action="allow"),
            ApprovalRule(pattern="list_directory", action="allow"),
            ApprovalRule(pattern="search_files", action="allow"),
            ApprovalRule(pattern="search_web", action="allow"),
            ApprovalRule(pattern="fetch_url", action="allow"),
            ApprovalRule(pattern="save_memory", action="allow"),
            ApprovalRule(pattern="get_memory", action="allow"),
            ApprovalRule(pattern="search_memory", action="allow"),
            ApprovalRule(pattern="execute_bash", action="ask"),
            ApprovalRule(pattern="write_file", action="ask"),
            ApprovalRule(pattern="edit_file", action="ask"),
            ApprovalRule(pattern="delete_file", action="deny"),
        ]

    def check(self, tool_name: str) -> str:
        """Check if tool needs approval. Returns: allow, ask, deny."""
        for rule in self.rules:
            if rule.pattern == tool_name:
                return rule.action
        return "ask"  # default: ask

    def add_rule(self, pattern: str, action: str):
        self.rules.append(ApprovalRule(pattern=pattern, action=action))

    def list_rules(self) -> list[dict]:
        return [{"pattern": r.pattern, "action": r.action} for r in self.rules]
