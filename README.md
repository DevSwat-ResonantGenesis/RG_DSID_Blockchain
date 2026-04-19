# RG_DSID_Blockchain

> **Part of the [DevSwat](https://dev-swat.com) platform** — Internal DSID-P blockchain: hash lineage, transaction graph, audit chain, and Base Sepolia anchoring.

[![Status: Production](https://img.shields.io/badge/Status-Production-brightgreen.svg)]()
[![Port: 8000](https://img.shields.io/badge/Port-8000-orange.svg)]()
[![Database: PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL-336791.svg)]()
[![License: RG Source Available](https://img.shields.io/badge/License-RG%20Source%20Available-blue.svg)](LICENSE.txt)

**Internal** blockchain service for the platform. Manages DSID-P (Digital State Identity Protocol), hash lineage tracking, transaction graphs, audit chains, and merkle root anchoring to Base Sepolia.

> **Not to be confused with:**
> - **RG_DSID_Node** — External decentralized node runtime (Base Sepolia, agent execution, P2P, port 8081)
> - **RG_external_blockchain** — External chain bridges (Raft consensus, P2P gossip, block production)

## Features

- **DSID-P** — Digital State Identity Protocol for content hashing and lineage
- **Block mining** — Background miner with configurable intervals
- **Transaction graph** — Full transaction history and lineage tracking
- **Audit chain** — Immutable audit trail for all platform operations
- **External anchoring** — Periodic merkle root anchoring to Base Sepolia
- **Distributed consensus** — Multi-node consensus protocol
- **Smart contracts** — On-chain smart contract execution
- **Identity registry** — Crypto identity Layer 4 registry
- **DSID backfill** — Automatic backfill of existing DSIDs into blockchain

## Quick Start

```bash
pip install -r requirements.txt
export DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/blockchain"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Deployment

- **Server path**: `/home/deploy/RG_DSID_Blockchain`
- **Docker service**: `blockchain_service`
- **Container**: `blockchain_service` | **Port**: 8000

---
**Organization**: [DevSwat-ResonantGenesis](https://github.com/DevSwat-ResonantGenesis) | **Platform**: [dev-swat.com](https://dev-swat.com)
