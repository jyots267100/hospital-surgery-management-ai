"""Centralized application configuration, loaded from environment variables."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # LLM provider
    llm_provider: str = "gemini"

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"

    # RAG / embeddings
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    chroma_persist_directory: str = "./chroma_data"
    chroma_collection_name: str = "hospital_policies"
    chunk_size: int = 1000
    chunk_overlap: int = 150
    retrieval_top_k: int = 5

    # App
    app_env: str = "development"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_base_url: str = "http://localhost:8000"

    # Data paths
    data_dir: str = "./data"
    policy_docs_dir: str = "./policies"

    @property
    def data_path(self) -> Path:
        return Path(self.data_dir)

    @property
    def policy_docs_path(self) -> Path:
        return Path(self.policy_docs_dir)


@lru_cache
def get_settings() -> Settings:
    return Settings()
