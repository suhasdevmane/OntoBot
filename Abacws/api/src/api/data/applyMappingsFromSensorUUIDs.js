/*
 Bulk-create device mappings for MySQL sensordb.sensor_data from sensor_uuids.txt.

 Assumptions:
 - API is running at API_URL (default http://localhost:5000/api)
 - API_KEY set in env if routes are protected (x-api-key header)
 - MySQL datastore is used by the API (DB_ENGINE=mysql) OR the datastore supports mappings for the chosen engine
 - The MySQL server used by the API has two databases:
     - abacws (internal tables: devices, device_timeseries_mappings, data_sources)
     - sensordb (external telemetry table: sensor_data)
 - Telemetry table schema (long/narrow):
     CREATE TABLE sensordb.sensor_data (
       id INT AUTO_INCREMENT PRIMARY KEY,
       sensor_name VARCHAR(255),
       sensor_uuid VARCHAR(36),
       value FLOAT,
       unit VARCHAR(20),
       ts TIMESTAMP,
       INDEX idx_sensor_ts (sensor_name, ts),
       INDEX idx_uuid_ts (sensor_uuid, ts)
     );

 Usage examples:
   # Default: map Air_Quality_Level_Sensor_* to each node_5.xx
   node /api/src/api/data/applyMappingsFromSensorUUIDs.js

   # Choose a different sensor family (e.g., CO2)
   SENSOR_PREFIX=CO2_Level_Sensor node /api/src/api/data/applyMappingsFromSensorUUIDs.js

   # Dry-run verification only (no create)
   DRY_RUN=true node /api/src/api/data/applyMappingsFromSensorUUIDs.js

   # Custom API host/port and MySQL DS connection details
   API_URL=http://localhost:5000/api \
   DS_NAME=abacws-mysql-sensordb DS_HOST=mysqlserver DS_PORT=3306 DS_DB=sensordb \
   DS_USER=root DS_PASSWORD=mysql \
   node /api/src/api/data/applyMappingsFromSensorUUIDs.js

  # Pivot mode (wide table where each sensor UUID is a column and timestamp column is 'Datetime')
  # This sets device_id_column=COLUMN and uses each UUID as the value column for its mapping
  API_URL=http://localhost:5000/api \
  FAMILIES=ALL DEVICE_ID_COLUMN=COLUMN TIMESTAMP_COLUMN=Datetime \
  node /api/src/api/data/applyMappingsFromSensorUUIDs.js
*/

// Node 18+ has global fetch
const fs = require('fs');
const path = require('path');

const API_URL = process.env.API_URL || 'http://localhost:5000/api';
const API_KEY = process.env.API_KEY || process.env.X_API_KEY || '';
const DRY_RUN = String(process.env.DRY_RUN || 'false').toLowerCase() === 'true';
// Backward-compat: SENSOR_PREFIX maps a single family; new FAMILIES allows multi-family (comma-separated) or 'ALL'
const SENSOR_PREFIX = process.env.SENSOR_PREFIX || 'Air_Quality_Level_Sensor';
const FAMILIES = process.env.FAMILIES || '';
// If true, allow multiple mappings per device by creating per-family Data Sources (suffixing DS name)
// Caution: Backend enforces UNIQUE(device_name, data_source_id); per-family DS avoids conflicts.
const MULTI_DS_PER_DEVICE = String(process.env.MULTI_DS_PER_DEVICE || 'false').toLowerCase() === 'true';

// Data source connection (assumes API engine=mysql and same MySQL server)
const DS_NAME = process.env.DS_NAME || 'abacws-mysql-sensordb';
const DS_HOST = process.env.DS_HOST || 'mysqlserver';
const DS_PORT = Number(process.env.DS_PORT || 3306);
const DS_DB = process.env.DS_DB || 'sensordb';
const DS_SCHEMA = process.env.DS_SCHEMA || DS_DB; // mysql.js uses schema_name as DB name
const DS_USER = process.env.DS_USER || 'root';
const DS_PASSWORD = process.env.DS_PASSWORD || 'mysql';

const TABLE_NAME = process.env.TABLE_NAME || 'sensor_data';
const DEVICE_ID_COLUMN = process.env.DEVICE_ID_COLUMN || 'sensor_uuid';
let TIMESTAMP_COLUMN = process.env.TIMESTAMP_COLUMN || 'ts';
const VALUE_COLUMNS = (process.env.VALUE_COLUMNS || 'value').split(',').map(s=>s.trim()).filter(Boolean);
const PRIMARY_VALUE_COLUMN = process.env.PRIMARY_VALUE_COLUMN || VALUE_COLUMNS[0] || 'value';

const PIVOT_MODE = String(DEVICE_ID_COLUMN).toUpperCase() === 'COLUMN';
if (PIVOT_MODE && (!process.env.TIMESTAMP_COLUMN || TIMESTAMP_COLUMN === 'ts')) {
  // Sensible default for wide sensordb.sensor_data
  TIMESTAMP_COLUMN = 'Datetime';
}

function readSensorUUIDs() {
  // Prefer rasa-bldg1/actions/sensor_uuids.txt; fallback to cwd
  const candidates = [
    path.resolve(__dirname, '../../../../rasa-bldg1/actions/sensor_uuids.txt'),
    path.resolve(process.cwd(), 'sensor_uuids.txt')
  ];
  const file = candidates.find(f => fs.existsSync(f));
  if (!file) throw new Error('sensor_uuids.txt not found (expected under rasa-bldg1/actions or CWD)');
  const lines = fs.readFileSync(file, 'utf-8').split(/\r?\n/).map(l => l.trim()).filter(Boolean);
  const rows = [];
  for (const line of lines) {
    const [name, uuid] = line.split(',').map(s => s && s.trim());
    if (!name || !uuid) continue;
    rows.push({ name, uuid });
  }
  return rows;
}

async function listDataSources() {
  const res = await fetch(`${API_URL}/datasources`);
  if (!res.ok) throw new Error(`GET datasources failed: ${res.status}`);
  return res.json();
}

async function createDataSource(nameOverride) {
  const payload = {
    name: nameOverride || DS_NAME,
    host: DS_HOST,
    port: DS_PORT,
    database: DS_DB,
    schema: DS_SCHEMA,
    username: DS_USER,
    password: DS_PASSWORD,
    ssl: false,
  };
  const res = await fetch(`${API_URL}/datasources`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(API_KEY? { 'x-api-key': API_KEY } : {}) },
    body: JSON.stringify(payload)
  });
  if (!res.ok) throw new Error(`POST datasources failed: ${res.status}`);
  return res.json();
}

async function ensureDataSource(nameOverride) {
  const name = nameOverride || DS_NAME;
  const list = await listDataSources();
  const found = list.find(d => d.name === name);
  if (found) return found;
  return await createDataSource(name);
}

async function verifyMapping(sample) {
  const res = await fetch(`${API_URL}/mappings/verify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(API_KEY? { 'x-api-key': API_KEY } : {}) },
    body: JSON.stringify(sample)
  });
  const out = await res.json().catch(() => ({}));
  if (!res.ok || out.error) return { ok: false, error: out.error || `HTTP ${res.status}` };
  return { ok: true, rows: out.rows || [], sql: out.sql };
}

async function createMapping(payload) {
  const res = await fetch(`${API_URL}/mappings`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(API_KEY? { 'x-api-key': API_KEY } : {}) },
    body: JSON.stringify(payload)
  });
  if (res.status === 409) return { ok: true, status: 'exists' };
  if (!res.ok) {
    const txt = await res.text().catch(()=> '');
    return { ok: false, error: `HTTP ${res.status} ${txt}` };
  }
  const json = await res.json();
  return { ok: true, status: 'created', id: json.id };
}

function toDeviceName(sensorName) {
  // Expect sensorName like "Air_Quality_Level_Sensor_5.04" -> device "node_5.04"
  const m = sensorName.match(/_(\d+\.\d+)$/);
  if (!m) return null;
  return `node_${m[1]}`;
}

function groupByFamilies(rows){
  // Derive family prefix before trailing _5.xx
  const fams = new Map();
  for(const r of rows){
    const m = r.name.match(/^(.*)_\d+\.\d+$/);
    if(!m) continue;
    const fam = m[1];
    if(!fams.has(fam)) fams.set(fam, []);
    fams.get(fam).push(r);
  }
  return fams;
}

async function ensureMappingsForFamily(family, rows){
  const dsName = MULTI_DS_PER_DEVICE ? `${DS_NAME}__${family}`.slice(0,128) : DS_NAME;
  const ds = await ensureDataSource(dsName);
  console.log(`[applyMappings] Data Source ready for family '${family}': id=${ds.id} name=${ds.name}`);

  let created = 0, existed = 0, failed = 0, verified = 0, skipped = 0;
  for (const row of rows) {
    const deviceName = toDeviceName(row.name);
    if (!deviceName) { console.warn(`Skipping unparseable name '${row.name}'`); skipped++; continue; }
    const sample = {
      data_source_id: ds.id,
      table_name: TABLE_NAME,
      device_id_column: DEVICE_ID_COLUMN,
      device_identifier_value: row.uuid,
      timestamp_column: TIMESTAMP_COLUMN,
      value_columns: PIVOT_MODE ? [row.uuid] : VALUE_COLUMNS,
    };
    const check = await verifyMapping(sample).catch(() => ({ ok:false }));
    if (check.ok) { verified++; }
    else { console.warn(`[applyMappings] Verify failed for ${deviceName} (${row.uuid}): ${check.error||'unknown'}`); }

    if (DRY_RUN) continue;

    const payload = {
      device_name: deviceName,
      data_source_id: ds.id,
      table_name: TABLE_NAME,
      device_id_column: DEVICE_ID_COLUMN,
      device_identifier_value: row.uuid,
      timestamp_column: TIMESTAMP_COLUMN,
      value_columns: PIVOT_MODE ? [row.uuid] : VALUE_COLUMNS,
      primary_value_column: PIVOT_MODE ? row.uuid : PRIMARY_VALUE_COLUMN,
    };
    const res = await createMapping(payload);
    if (!res.ok) { console.error(`[applyMappings] Create failed for ${deviceName}: ${res.error}`); failed++; continue; }
    if (res.status === 'exists') existed++; else created++;
  }
  console.log(`[applyMappings] Family '${family}' => created=${created} existed=${existed} verified_ok=${verified} failed=${failed} skipped=${skipped}`);
}

(async () => {
  try {
    const all = readSensorUUIDs();
    const byFam = groupByFamilies(all);

    // Determine which families to process
    let familiesToProcess = [];
    if (FAMILIES && FAMILIES.toUpperCase() !== 'ALL') {
      familiesToProcess = FAMILIES.split(',').map(s=>s.trim()).filter(Boolean);
    } else if (FAMILIES.toUpperCase() === 'ALL') {
      familiesToProcess = Array.from(byFam.keys());
    } else {
      // Backward-compat single-family default
      familiesToProcess = [SENSOR_PREFIX];
    }

    // Second pass behavior: if a single SENSOR_PREFIX is provided AND ALSO_FAMILIES is set, do primary + extras
    const ALSO = (process.env.ALSO_FAMILIES || '').split(',').map(s=>s.trim()).filter(Boolean);
    if (!FAMILIES && ALSO.length) familiesToProcess = [SENSOR_PREFIX, ...ALSO];

    // Filter only existing families present in file
    const existingFamilies = familiesToProcess.filter(f => byFam.has(f));
    const missingFamilies = familiesToProcess.filter(f => !byFam.has(f));
    if (missingFamilies.length) console.warn(`[applyMappings] Families not found in file (skipped): ${missingFamilies.join(', ')}`);
    if (!existingFamilies.length) { console.warn('[applyMappings] No matching families to process. Nothing to do.'); return; }

    console.log(`[applyMappings] Families to process (${existingFamilies.length}): ${existingFamilies.join(', ')}`);
    if (MULTI_DS_PER_DEVICE) console.log(`[applyMappings] Multi-DS mode enabled: creating per-family data sources to allow multiple mappings per device.`);

    for (const fam of existingFamilies) {
      const rows = byFam.get(fam);
      await ensureMappingsForFamily(fam, rows);
    }

    // Show a sample of /latest
    try {
      const latestRes = await fetch(`${API_URL}/latest`);
      if (latestRes.ok) {
        const latest = await latestRes.json();
        const oneKey = Object.keys(latest)[0];
        if (oneKey) console.log(`[applyMappings] Sample latest: ${oneKey} ->`, latest[oneKey]);
        else console.log('[applyMappings] /latest returned empty (no recent data in lookback window)');
      } else {
        console.warn(`[applyMappings] GET /latest failed: ${latestRes.status}`);
      }
    } catch(_){}
  } catch (e) {
    console.error('[applyMappings] Error:', e.message || e);
    process.exitCode = 1;
  }
})();
