# Synthetic Building (bldg3)

This folder contains a synthetic building configuration used to validate OntoBot’s multi‑building workflow. It mirrors the Abacws pattern but uses Cassandra for telemetry storage and focuses on Brick 1.4 TTLs created with Protégé/Brickly and Python brickschema utilities.

> Purpose: Provide a reproducible synthetic building bundle (ontology + datasets + notes) backed by Cassandra.

## What lives here

- Brick 1.4 ontology files (TTL) for the synthetic building
- Sensor lists and UUID mappings for this building
- Example datasets and notebooks/scripts used to construct and validate the TTL
- Rasa training artifacts derived from the building’s canonical sensor names

## Data ingestion and storage (Cassandra)

- Source: Synthetic telemetry representing sensors/devices
- Storage: Telemetry is stored in Cassandra tables designed for timeseries queries
- Normalization: Partitions/primary keys include a stable sensor UUID aligned with the Brick TTL; clustering keys support time‑range queries

## Knowledge base (Brick 1.4 TTL)

- TTLs are authored using:
  - Protégé and/or the Brickly package for interactive modeling
  - Python brickschema/rdflib for scripted generation/validation
- Reference: Brick 1.4 vocabulary → https://ontology.brickschema.org/
- Deployment: Load TTLs into Apache Jena Fuseki and expose a dataset for SPARQL queries

## Rasa model and NLU

- Canonical sensor names (from TTL) are used to train intents/entities in Rasa
- Actions perform SPARQL lookups to resolve entities and retrieve timeseries UUIDs
- Analytics payloads are built with units and UK guidelines when applicable

## SPARQL usage

- SPARQL queries resolve building metadata (spaces, equipment, sensors) and back references for timeseries
- Fuseki endpoints are shared across buildings; swap the dataset to target bldg3

## Typical workflow

1) Build/refresh the Brick 1.4 TTL with Protégé/Brickly or Python scripts
2) Load it into Fuseki and validate basic queries
3) Ensure Cassandra contains the synthetic telemetry keyed by the UUIDs referenced in TTL
4) Train the Rasa model with the canonical names
5) Ask questions; Actions resolve entities via SPARQL and run analytics against Cassandra

## Notes

- Large raw datasets are not versioned; prefer small samples or external storage/LFS
- Jupyter checkpoints remain ignored; commit only curated notebooks
- Keep building‑specific mappings unique to avoid cross‑building collisions

## References

- Brick Schema 1.4: https://ontology.brickschema.org/
- Apache Jena Fuseki: https://jena.apache.org/documentation/fuseki2/
- Rasa: https://rasa.com/docs/rasa/
- Apache Cassandra: https://cassandra.apache.org/doc/latest/

## See also

- Root `README.md` for stack and quick start
- `bldg1/README.md` for the Abacws example (PostgreSQL/ThingsBoard)
- `bldg2/README.md` for the MySQL synthetic variant

---

## Quick start (Building 3 stack)

Start the bldg3 stack (Rasa at `./rasa-bldg3`, ThingsBoard on Cassandra, shared services):

```powershell
docker compose -f docker-compose.bldg3.yml up -d --build
```

Key endpoints (host):
- ThingsBoard UI: http://localhost:8083
- Device HTTP API: http://localhost:8082 (proxied to TB 8081)
- MQTT: localhost:1884
- Rasa: http://localhost:5006/version
- Actions: http://localhost:5056/health
- Duckling: http://localhost:8001/
- File server: http://localhost:8084/health
- Rasa Editor: http://localhost:6081/
- Fuseki (SPARQL): http://localhost:3030/
- pgAdmin: http://localhost:5051/

## Load your TTL dataset into Fuseki

The compose mounts `./bldg3/trial/dataset` into the Fuseki container. Open http://localhost:3030 and:
- Create or select a dataset
- Upload the TTL files from the mounted path (inside container `/fuseki-data`)
- Run a quick SPARQL to verify classes/instances

## ThingsBoard: create device and send telemetry

1) Open TB UI: http://localhost:8083 and login as Tenant Admin (tenant@thingsboard.org / tenant).
2) Devices → Add a device (e.g., `B3_TestDevice`), open it → “Copy access token”.
3) Send a telemetry message via HTTP (replace `<DEVICE_TOKEN>`):

```powershell
Invoke-WebRequest -Method Post -Uri "http://localhost:8082/api/v1/<DEVICE_TOKEN>/telemetry" -ContentType "application/json" -Body '{ "temperature": 23.7, "humidity": 55 }'
```

Check “Latest Telemetry” for your device in the TB UI.

## pgAdmin connections (TB Postgres metadata)

Open pgAdmin at http://localhost:5051. The server is auto-registered via `bldg3/servers.json`:

- TB Postgres (bldg3) → Host: `tb_postgres`, Port: `5432`
  - Username: `thingsboard`
  - Password: `thingsboard`
  - Database: `thingsboard` (select after connecting; maintenance DB defaults to `postgres`)

Map device token → device UUID (run in DB `thingsboard`):

```sql
SELECT d.id, d.name
FROM device d
JOIN device_credentials dc ON dc.device_id = d.id
WHERE dc.credentials_id = 'YOUR_DEVICE_ACCESS_TOKEN';
```

Use the UUID in TB dashboards/APIs as needed. Remember: in bldg3, telemetry lives in Cassandra; Postgres holds TB metadata only.

## Cassandra: basic validation

To explore the Cassandra schema and validate telemetry at a low level, open a cqlsh session in the container:

```powershell
docker compose -f docker-compose.bldg3.yml exec cassandra cqlsh -u cassandra -p cassandra
```

Inside cqlsh:

```sql
DESCRIBE KEYSPACES;
USE thingsboard;
-- List tables in the ThingsBoard keyspace
SELECT table_name FROM system_schema.tables WHERE keyspace_name='thingsboard';
-- Inspect a small sample (table names can differ by TB version)
-- Example (adjust to what you find):
-- SELECT * FROM ts_kv_latest_cf LIMIT 10;
```

Notes:
- Table names may vary by ThingsBoard version; prefer TB UI dashboards and APIs for routine telemetry verification.
- The compose exposes Cassandra on localhost:9042 if you use host tools.

## Rasa: train and test (bldg3)

Manual training job (one-off container):

```powershell
docker compose -f docker-compose.bldg3.yml --profile manual up --build --abort-on-container-exit rasa-train
```

Quick REST test against Rasa:

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:5006/webhooks/rest/webhook -ContentType 'application/json' -Body (@{
  sender = 'tester_b3'
  message = 'Show humidity trends for last week in Zone B'
} | ConvertTo-Json)
```

## Troubleshooting

- Cassandra warm-up: first start may take ~1–2 minutes; the container becomes healthy when nodetool shows `UN`.
- TB roles: use Tenant Admin (tenant@thingsboard.org / tenant) to view tenant devices and telemetry.
- Fuseki: ensure dataset is loaded at http://localhost:3030 before running SPARQL from actions.
- pgAdmin: default login `pgadmin@example.com` / `admin`; server is pre-registered, select DB `thingsboard`.
- Ports: run only one building stack at a time to avoid conflicts, or adjust host port mappings in the compose.
