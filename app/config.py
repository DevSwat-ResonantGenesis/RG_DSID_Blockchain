"""Blockchain Service configuration."""

import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"postgresql+asyncpg://{os.getenv('BLOCKCHAIN_DB_USER', 'postgres')}:"
        f"{os.getenv('BLOCKCHAIN_DB_PASSWORD', 'postgres')}@"
        f"{os.getenv('BLOCKCHAIN_DB_HOST', 'db')}:"
        f"{os.getenv('BLOCKCHAIN_DB_PORT', '5432')}/"
        f"{os.getenv('BLOCKCHAIN_DB_NAME', 'resonant_blockchain')}?ssl=require"
    )
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379/2")
    
    # Blockchain configuration
    CHAIN_ID: str = "resonant-genesis-1"
    BLOCK_TIME_SECONDS: int = 10
    MAX_TRANSACTIONS_PER_BLOCK: int = 1000
    
    # DSID-P configuration
    DSID_PREFIX: str = "dsid"
    DSID_VERSION: int = 1
    
    # Hash configuration
    HASH_ALGORITHM: str = "sha256"
    MERKLE_TREE_ALGORITHM: str = "sha256"
    
    # Anchoring (external blockchain)
    ANCHOR_ENABLED: bool = os.getenv("ANCHOR_ENABLED", "false").lower() == "true"
    ANCHOR_CHAIN: str = os.getenv("ANCHOR_CHAIN", "ethereum")
    ANCHOR_RPC_URL: str = os.getenv("ANCHOR_RPC_URL", "")
    ANCHOR_CONTRACT_ADDRESS: str = os.getenv("ANCHOR_CONTRACT_ADDRESS", "")
    
    class Config:
        env_file = ".env"


settings = Settings()
