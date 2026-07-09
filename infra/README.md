# 🛠️ infra — Containerization & Deployment Orchestration

This folder contains container definitions and orchestration scripts to run and scale the **Criminal Agent Platform**.

---

## 📁 Folder Contents

```
infra/
├── docker/
│   ├── web.Dockerfile        # Production Dockerfile for the Next.js web application
│   ├── api.Dockerfile        # Production Dockerfile for the FastAPI backend service
│   └── celery.Dockerfile     # Production Dockerfile for Celery background tasks & workers
└── k8s/
    ├── postgres-deployment.yaml   # Config for PostgreSQL/PostGIS databases
    ├── neo4j-deployment.yaml      # Config for Neo4j Graph database
    ├── redis-deployment.yaml      # Config for Celery task queuing and caching
    ├── api-deployment.yaml        # Config for FastAPI microservices
    ├── web-deployment.yaml        # Config for Next.js frontend load balancer
    └── keycloak-deployment.yaml   # Config for SSO and IAM (Keycloak)
```

---

## 🔒 Production Security Note
PII and sensitive criminal record data (CCTNS/FIRs) must be hosted on state-owned cloud data centers or on-premises networks. Deployment is designed to target government environments such as **NIC MeghRaj** or local state infrastructure.
