"""FastAPI dependency providers (singletons per process)."""

from __future__ import annotations

from functools import lru_cache

from app.config import Settings, get_settings
from db.graphdb_client import GraphDBClient
from db.neo4j_client import Neo4jClient
from llm.client import LLMClient


@lru_cache
def get_neo4j() -> Neo4jClient:
    return Neo4jClient(get_settings())


@lru_cache
def get_graphdb() -> GraphDBClient:
    return GraphDBClient(get_settings())


@lru_cache
def get_llm() -> LLMClient:
    return LLMClient(get_settings())


def settings() -> Settings:
    return get_settings()
