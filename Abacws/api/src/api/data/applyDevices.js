/*
 Upsert devices from the local devices.json into the running API via HTTP.
 Designed to run inside the abacws-api container (or host) without rebuild.

 Usage examples:
   # Inside container (uses bind-mounted /api/src/api/data)
   node /api/src/api/data/applyDevices.js

   # Control API URL and offset behavior
   API_URL=http://localhost:5000/api SUBTRACT_OFFSET=false node /api/src/api/data/applyDevices.js

 Env vars:
   API_URL          Default: http://localhost:5000/api
   SUBTRACT_OFFSET  Default: false. If true, subtracts devices.json.offset from positions before sending.
*/

// Node 18+ has global fetch
const fs = require('fs');
const path = require('path');

const API_URL = process.env.API_URL || 'http://localhost:5000/api';
const SUBTRACT_OFFSET = String(process.env.SUBTRACT_OFFSET || 'false').toLowerCase() === 'true';

function readDevicesJson() {
  const file = path.resolve(__dirname, 'devices.json');
  const text = fs.readFileSync(file, 'utf-8');
  const json = JSON.parse(text);
  if (!json || !Array.isArray(json.devices)) throw new Error('devices.json missing devices[]');
  const offset = json.offset || { x: 0, y: 0, z: 0 };
  return { devices: json.devices, offset };
}

function normalizePosition(pos, offset) {
  if (!SUBTRACT_OFFSET) return pos;
  return {
    x: Number(pos.x) - Number(offset.x || 0),
    y: Number(pos.y) - Number(offset.y || 0),
    z: Number(pos.z) - Number(offset.z || 0),
  };
}

async function getDevice(name) {
  const res = await fetch(`${API_URL}/devices/${encodeURIComponent(name)}`);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`GET ${name} failed: ${res.status}`);
  return res.json();
}

async function createDevice(doc) {
  const res = await fetch(`${API_URL}/devices`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(doc),
  });
  if (!res.ok) throw new Error(`POST ${doc.name} failed: ${res.status}`);
  return res.json();
}

async function patchDevice(name, patch) {
  const res = await fetch(`${API_URL}/devices/${encodeURIComponent(name)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  });
  if (!res.ok) throw new Error(`PATCH ${name} failed: ${res.status}`);
  return res.json();
}

function diffPatch(existing, desired) {
  const patch = {};
  if (desired.type !== undefined && desired.type !== existing.type) patch.type = desired.type;
  if (desired.floor !== undefined && Number(desired.floor) !== Number(existing.floor)) patch.floor = Number(desired.floor);
  if (desired.pinned !== undefined && !!desired.pinned !== !!existing.pinned) patch.pinned = !!desired.pinned;
  if (desired.position) {
    const ex = existing.position || {};
    const dp = desired.position;
    if (Number(ex.x) !== Number(dp.x) || Number(ex.y) !== Number(dp.y) || Number(ex.z) !== Number(dp.z)) {
      patch.position = { x: Number(dp.x), y: Number(dp.y), z: Number(dp.z) };
    }
  }
  return patch;
}

(async () => {
  try {
    const { devices, offset } = readDevicesJson();
    let created = 0, updated = 0, skipped = 0;
    for (const d of devices) {
      const desired = {
        name: String(d.name),
        type: d.type !== undefined ? String(d.type) : undefined,
        floor: Number(d.floor),
        pinned: typeof d.pinned === 'boolean' ? d.pinned : undefined,
        position: normalizePosition({ x: d.position?.x || 0, y: d.position?.y || 0, z: d.position?.z || 0 }, offset),
      };
      if (!desired.name) { console.warn('Skipping device with empty name'); continue; }
      if (Number.isNaN(desired.floor)) { console.warn(`Skipping ${desired.name}: invalid floor`); continue; }
      const existing = await getDevice(desired.name).catch(e => { throw e; });
      if (!existing) {
        await createDevice({
          name: desired.name,
          type: desired.type,
          floor: desired.floor,
          position: desired.position,
          pinned: desired.pinned === undefined ? false : desired.pinned,
        });
        created++;
        continue;
      }
      const patch = diffPatch(existing, desired);
      if (Object.keys(patch).length === 0) { skipped++; continue; }
      await patchDevice(desired.name, patch);
      updated++;
    }
    console.log(`[applyDevices] Done. created=${created} updated=${updated} unchanged=${skipped}`);
  } catch (e) {
    console.error('[applyDevices] Error:', e.message || e);
    process.exitCode = 1;
  }
})();
