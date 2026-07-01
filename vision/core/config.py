"""Configuration management for Vision."""

import json
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class LLMConfig:
    provider: str = "ollama"
    model: str = "qwen2.5:14b"
    base_url: str = "http://localhost:11434"
    api_key: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096


@dataclass
class VoiceConfig:
    enabled: bool = False
    stt_engine: str = "faster-whisper"
    tts_engine: str = "edge-tts"
    tts_voice: str = "ru-RU-SvetlanaNeural"
    language: str = "ru"
    sample_rate: int = 16000
    silence_threshold: float = 0.01


@dataclass
class GestureConfig:
    enabled: bool = False
    camera_index: int = 0
    confidence: float = 0.7
    workspace_top: float = 0.15
    workspace_bottom: float = 0.75


@dataclass
class GatewayConfig:
    host: str = "0.0.0.0"
    port: int = 8080
    ws_port: int = 8081
    auth_token: str = ""


@dataclass
class Config:
    llm: LLMConfig = field(default_factory=LLMConfig)
    voice: VoiceConfig = field(default_factory=VoiceConfig)
    gestures: GestureConfig = field(default_factory=GestureConfig)
    gateway: GatewayConfig = field(default_factory=GatewayConfig)
    db_path: str = "vision.db"
    skills_dir: str = "skills"
    log_level: str = "INFO"

    @classmethod
    def load(cls, path: str | Path = "config.json") -> "Config":
        path = Path(path)
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            cfg = cls()
            if "llm" in data:
                for k, v in data["llm"].items():
                    if hasattr(cfg.llm, k):
                        setattr(cfg.llm, k, v)
            if "voice" in data:
                for k, v in data["voice"].items():
                    if hasattr(cfg.voice, k):
                        setattr(cfg.voice, k, v)
            if "gestures" in data:
                for k, v in data["gestures"].items():
                    if hasattr(cfg.gestures, k):
                        setattr(cfg.gestures, k, v)
            if "gateway" in data:
                for k, v in data["gateway"].items():
                    if hasattr(cfg.gateway, k):
                        setattr(cfg.gateway, k, v)
            return cfg
        return cls()

    def save(self, path: str | Path = "config.json"):
        path = Path(path)
        data = {
            "llm": self.llm.__dict__,
            "voice": self.voice.__dict__,
            "gestures": self.gestures.__dict__,
            "gateway": self.gateway.__dict__,
            "db_path": self.db_path,
            "skills_dir": self.skills_dir,
            "log_level": self.log_level,
        }
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
