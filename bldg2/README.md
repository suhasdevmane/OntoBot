# Synthetic Building (bldg2)

This folder contains a synthetic building configuration used to validate OntoBot’s multi‑building workflow. It mirrors the Abacws pattern but uses MySQL for telemetry storage and focuses on Brick 1.4 TTLs created with Protégé/Brickly and Python brickschema utilities.

> Purpose: Provide a reproducible synthetic building bundle (ontology + datasets + notes) backed by MySQL.

## What lives here

- Brick 1.4 ontology files (TTL) for the synthetic building
- Sensor lists and UUID mappings for this building
- Example datasets and notebooks/scripts used to construct and validate the TTL
- Rasa training artifacts derived from the building’s canonical sensor names

## Data ingestion and storage (MySQL)

- Source: Synthetic telemetry representing sensors/devices
- Storage: In this variant, telemetry is stored in MySQL (the demo stack maps host 3307 → container 3306)
- Normalization: Raw readings are reshaped to a canonical table form keyed by UUIDs that correspond to entities in the TTL

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
- Fuseki endpoints are shared across buildings; swap the dataset to target bldg2

## Typical workflow

1) Build/refresh the Brick 1.4 TTL with Protégé/Brickly or Python scripts
2) Load it into Fuseki and validate basic queries
3) Ensure MySQL contains the synthetic telemetry keyed by the UUIDs referenced in TTL
4) Train the Rasa model with the canonical names
5) Ask questions; Actions resolve entities via SPARQL and run analytics against MySQL

## Notes

- Large raw datasets are not versioned; prefer small samples or external storage/LFS
- Jupyter checkpoints remain ignored; commit only curated notebooks
- Keep building‑specific mappings unique to avoid cross‑building collisions

## References

- Brick Schema 1.4: https://ontology.brickschema.org/
- Apache Jena Fuseki: https://jena.apache.org/documentation/fuseki2/
- Rasa: https://rasa.com/docs/rasa/
- MySQL: https://dev.mysql.com/doc/

## See also

- Root `README.md` for stack and quick start
- `bldg1/README.md` for the Abacws example (PostgreSQL/ThingsBoard)

---

## ThingsBoard + TimescaleDB: send telemetry and verify storage

Although bldg2 focuses on MySQL storage, you may run the separate ThingsBoard + TimescaleDB option from the repo root and validate end-to-end telemetry. This section captures the exact commands (PowerShell-friendly) and SQL checks discussed earlier.

### Start the Timescale option

```powershell
# From repo root
docker compose -f docker-compose.ts.yml up -d
docker compose -f docker-compose.ts.yml ps
```

Notes:
- The `timescaledb` service is Postgres with the Timescale extension; you don’t need an additional Postgres container.
- ThingsBoard connects to it via `SPRING_DATASOURCE_URL=jdbc:postgresql://timescaledb:5432/thingsboard`.

### Create a device and copy its Access Token

1) Open ThingsBoard UI: http://localhost:8082
2) Login as Tenant Admin (tenant@thingsboard.org / tenant)
3) Devices → add a device (e.g., `TestDevice`), open it, and click “Copy access token”.

Important: Use the Tenant Admin account to view/create devices and telemetry (System Admin won’t see tenant devices by default).

### Send telemetry

Pick one of the transports below.

#### Option A — HTTP (no installs)

PowerShell multiline (replace ACCESS_TOKEN):

```powershell
$body = @{ temperature = 23.7; humidity = 55 } | ConvertTo-Json -Compress
Invoke-RestMethod -Method Post `
  -Uri "http://localhost:8081/api/v1/ACCESS_TOKEN/telemetry" `
  -ContentType "application/json" `
  -Body $body
```

One‑liner:

```powershell
Invoke-RestMethod -Method Post -Uri "http://localhost:8081/api/v1/ACCESS_TOKEN/telemetry" -ContentType "application/json" -Body (@{ temperature = 23.7; humidity = 55 } | ConvertTo-Json -Compress)
```

If your image exposes device HTTP on 8080 instead, either:
- Post from inside Docker network (see curl container below), or
- Map port 8080 on host by adding `"8080:8080"` under `mytb.ports` in `docker-compose.ts.yml` and restarting the stack.

#### Option B — MQTT using Docker client (no host install)

Publish a message using an ephemeral mosquitto client container. Replace ACCESS_TOKEN.

```powershell
docker run --rm eclipse-mosquitto mosquitto_pub `
  -h host.docker.internal -p 1883 `
  -t "v1/devices/me/telemetry" `
  -u "ACCESS_TOKEN" `
  -m "{\"temperature\": 26}"
```

If you prefer to publish directly inside the Docker network (avoids host routing), target the service DNS name and attach the same network:

```powershell
docker run --rm --network ontobot-network eclipse-mosquitto mosquitto_pub `
  -h thingsboard -p 1883 `
  -t "v1/devices/me/telemetry" `
  -u "ACCESS_TOKEN" `
  -m "{\"temperature\": 26}"
```

#### Option C — HTTP using a Docker curl client (same network)

```powershell
docker run --rm --network ontobot-network curlimages/curl:8.7.1 curl -sS -v -X POST `
  http://thingsboard:8081/api/v1/ACCESS_TOKEN/telemetry `
  -H "Content-Type: application/json" `
  -d "{\"temperature\":23.7,\"humidity\":55}" `
  --connect-timeout 5
```

### Verify in the ThingsBoard UI

In the UI (Tenant Admin), open your device → “Latest Telemetry”. You should see the keys/values appear seconds after the publish.

### Verify in TimescaleDB with SQL

Open a psql shell:

```powershell
# Inside the DB container
docker compose -f docker-compose.ts.yml exec timescaledb psql -U thingsboard -d thingsboard

# Or from host if you have psql installed
psql -h localhost -p 5433 -U thingsboard -d thingsboard
```

Map token → device UUID:

```sql
SELECT d.id, d.name
FROM device d
JOIN device_credentials dc ON dc.device_id = d.id
WHERE dc.credentials_id = 'YOUR_DEVICE_ACCESS_TOKEN';
```

Recent telemetry rows (replace entity UUID):

```sql
SELECT
  to_timestamp(t.ts/1000.0) AS ts,
  dkey.key,
  COALESCE(
    t.dbl_v::text,
    t.long_v::text,
    t.str_v,
    (t.bool_v::text),
    (t.json_v::text)
  ) AS value
FROM ts_kv t
JOIN ts_kv_dictionary dkey ON t.key = dkey.key_id
WHERE t.entity_id = 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx'
ORDER BY t.ts DESC
LIMIT 20;
```

Latest cache (fast check):

```sql
SELECT d.name AS device,
       dkey.key,
       to_timestamp(tl.ts/1000.0) AS ts,
       COALESCE(
         tl.dbl_v::text,
         tl.long_v::text,
         tl.str_v,
         (tl.bool_v::text),
         (tl.json_v::text)
       ) AS value
FROM ts_kv_latest tl
JOIN ts_kv_dictionary dkey ON tl.key = dkey.key_id
JOIN device d ON d.id = tl.entity_id
WHERE d.id = 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx'
ORDER BY ts DESC;
```

Timescale checks (optional):

```sql
\dx;  -- should list timescaledb
SELECT hypertable_name
FROM timescaledb_information.hypertables
ORDER BY hypertable_name;
```

### Ingest wide CSV into TimescaleDB (ts_kv)

You can bulk-load the generated wide CSV (first column `datetime`, followed by UUID columns) into ThingsBoard’s SQL storage using the helper script we added.

PowerShell example (from repo root):

```powershell
$env:PG_HOST = 'localhost'
$env:PG_PORT = '5433'                  # host port mapped to timescaledb:5432
$env:PG_DATABASE = 'thingsboard'
$env:PG_USER = 'thingsboard'
$env:PG_PASSWORD = 'thingsboard'
$env:TB_DEVICE_NAME = 'TestDevice'     # or set TB_DEVICE_ID to a UUID

python bldg2/trial/dataset/ingest_wide_csv_to_timescale.py `
  bldg2/trial/dataset/synthetic_readings_wide.csv 2000
```

Notes:
- The script creates any missing keys in `ts_kv_dictionary` and inserts rows into `ts_kv` with ON CONFLICT DO NOTHING, making it safe to re-run.
- It expects a device to exist in ThingsBoard; set `TB_DEVICE_ID` or `TB_DEVICE_NAME` to target where telemetry lands.
- Values are parsed into dbl_v/long_v/bool_v/str_v automatically.
- For large files, the second argument controls the batch size (default 2000 timestamps per flush).

### Troubleshooting quick refs

- Ensure you’re logged in as Tenant Admin (tenant@thingsboard.org / tenant).
- Copy the device token exactly; wrong tokens silently drop data.
- Prefer valid JSON payloads: `{"temperature": 26}`.
- View logs:

```powershell
docker compose -f docker-compose.ts.yml logs --tail 200 mytb
docker compose -f docker-compose.ts.yml logs --tail 100 timescaledb
```

- If posting from host fails, use the Docker‑networked curl/mosquitto method to bypass host networking.

### if timescale db is not available or postgresql needed to upgraded by adding extension, following commands will help to create tables.

 Table: public.ts_kv

/ DROP TABLE IF EXISTS public.ts_kv;
```
CREATE TABLE IF NOT EXISTS public.ts_kv
(
    entity_id uuid NOT NULL,
    key integer NOT NULL,
    ts bigint NOT NULL,
    bool_v boolean,
    str_v character varying(10000000) COLLATE pg_catalog."default",
    long_v bigint,
    dbl_v double precision,
    json_v json,
    CONSTRAINT ts_kv_pkey PRIMARY KEY (entity_id, key, ts)
) PARTITION BY RANGE (ts);

ALTER TABLE IF EXISTS public.ts_kv
    OWNER to thingsboard;
```

/ Partitions SQL
```
CREATE TABLE public.ts_kv_2025_10 PARTITION OF public.ts_kv
    FOR VALUES FROM ('1759276800000') TO ('1761955200000')
TABLESPACE pg_default;

ALTER TABLE IF EXISTS public.ts_kv_2025_10
    OWNER to thingsboard;
CREATE TABLE public.ts_kv_indefinite PARTITION OF public.ts_kv
    DEFAULT
TABLESPACE pg_default;

ALTER TABLE IF EXISTS public.ts_kv_indefinite
    OWNER to thingsboard;
    ```