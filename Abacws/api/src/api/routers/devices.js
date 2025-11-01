const express = require("express");
const store = require('../datastore');
const { isDatastoreForcedDisabled } = require('./admin');
const { deviceMiddleware, apiKeyAuth } = require("../middleware");
const { upsertDevice } = require('../devicesFile');

const router = express.Router();
// Mount bulk export sub-route first to avoid conflict with :deviceName param
router.use('/', require('./devicesBulk'));

const listDevices = async (_req, res) => {
  const devices = await store.listDevices();
  res.status(200).json(devices);
};

// Basic payload validation
function validateDevicePayload(payload) {
  if (!payload || typeof payload !== 'object') return 'Invalid payload';
  const { name, type, floor, position, pinned } = payload;
  if (!name || typeof name !== 'string') return 'Missing or invalid name';
  if (type && typeof type !== 'string') return 'Invalid type';
  if (floor === undefined || floor === null || Number.isNaN(Number(floor))) return 'Missing or invalid floor';
  if (!position || typeof position !== 'object') return 'Missing position';
  const { x, y, z } = position;
  if ([x, y, z].some((v) => typeof v !== 'number' || Number.isNaN(v))) return 'Invalid position';
  if (pinned !== undefined && typeof pinned !== 'boolean') return 'Invalid pinned flag';
  return undefined;
}

// Create a device (POST /api/devices)
const createDevice = async (req, res, next) => {
  try {
    const err = validateDevicePayload(req.body);
    if (err) return res.status(400).json({ error: err });

    const doc = {
      name: String(req.body.name),
      type: req.body.type ? String(req.body.type) : undefined,
      floor: Number(req.body.floor),
      position: {
        x: Number(req.body.position.x),
        y: Number(req.body.position.y),
        z: Number(req.body.position.z),
      },
      pinned: typeof req.body.pinned === 'boolean' ? req.body.pinned : false,
    };
    if (isDatastoreForcedDisabled && isDatastoreForcedDisabled()) {
      return res.status(503).json({ error: 'Datastore disabled' });
    }
    try {
      const created = await store.createDevice(doc);
      // store implementations already sync devices.json via upsertDevice
      return res.status(201).json(created);
    } catch (e) {
      if (e.code === '23505') { // postgres unique violation
        return res.status(409).json({ error: 'Device name already exists' });
      }
      if (e?.code === 11000) { // mongo duplicate key
        return res.status(409).json({ error: 'Device name already exists' });
      }
      throw e;
    }
  } catch (e) {
    return next(e);
  }
};

const getDevice = async (req, res) => {
  if (isDatastoreForcedDisabled && isDatastoreForcedDisabled()) {
    return res.status(503).json({ error: 'Datastore disabled' });
  }
  const device = res.locals.device;
  res.status(200).json(device);
};

const getData = async (_req, res) => {
  if (isDatastoreForcedDisabled && isDatastoreForcedDisabled()) {
    return res.status(503).json({ error: 'Datastore disabled' });
  }
  const device = res.locals.device;
  // Prefer external (MySQL sensordb) sensor values if available
  try {
    if (store.engine === 'mysql' && typeof store.externalLatestForDevice === 'function') {
      const ext = await store.externalLatestForDevice(device.name);
      if (ext) return res.status(200).json(ext);
    }
  } catch(_) { /* ignore and fall back */ }
  const data = await store.latestDeviceData(device.name);
  res.status(200).json(data);
};

const getHistoricalData = async (req, res) => {
  if (isDatastoreForcedDisabled && isDatastoreForcedDisabled()) {
    return res.status(503).json({ error: 'Datastore disabled' });
  }
  const device = res.locals.device;
  const from = Number(req.query.from) || 0;
  const to = Number(req.query.to) || Date.now();
  // Prefer external (MySQL sensordb) sensor history if available
  try {
    if (store.engine === 'mysql' && typeof store.externalHistoryForDevice === 'function') {
      const hist = await store.externalHistoryForDevice(device.name, from, to, 10000);
      if (hist && Array.isArray(hist)) return res.status(200).json(hist);
    }
  } catch(_) { /* ignore and fall back */ }
  const history = await store.deviceHistory(device.name, from, to, 10000);
  res.status(200).json(history);
};

const addData = async (req, res) => {
  const device = res.locals.device;
  const data = req.body || {};
  data.timestamp = Date.now();
  await store.insertDeviceData(device.name, data);
  res.status(202).json();
};

const deleteData = async (_req, res) => {
  const device = res.locals.device;
  await store.deleteDeviceHistory(device.name);
  res.status(200).json();
};

// Update device (position/type/floor/pinned)
const updateDevice = async (req, res, next) => {
  try {
    const name = req.params.deviceName;
    const payload = req.body || {};

    const update = {};
    if (payload.type !== undefined) update.type = String(payload.type);
    if (payload.floor !== undefined) update.floor = Number(payload.floor);
    if (payload.position !== undefined) {
      const { x, y, z } = payload.position;
      if ([x, y, z].some((v) => typeof v !== 'number' || Number.isNaN(v))) {
        return res.status(400).json({ error: 'Invalid position' });
      }
      update.position = { x: Number(x), y: Number(y), z: Number(z) };
    }
    if (payload.pinned !== undefined) {
      if (typeof payload.pinned !== 'boolean') return res.status(400).json({ error: 'Invalid pinned flag' });
      update.pinned = payload.pinned;
    }
    if (Object.keys(update).length === 0) return res.status(400).json({ error: 'No fields to update' });

    if (isDatastoreForcedDisabled && isDatastoreForcedDisabled()) {
      return res.status(503).json({ error: 'Datastore disabled' });
    }
    const updated = await store.updateDevice(name, update);
    if (!updated) return res.status(404).json({ error: 'Device not found' });
    return res.status(200).json(updated);
  } catch (e) {
    return next(e);
  }
};

// Public listing
router.get("/", listDevices);

// Create device
router.post('/', /* apiKeyAuth, */ createDevice);

// Per-device routes
router.use("/:deviceName", deviceMiddleware);
router.get("/:deviceName", getDevice);

router.get("/:deviceName/data", getData);
router.put("/:deviceName/data", addData);

router.get("/:deviceName/history", getHistoricalData);
router.delete("/:deviceName/history", deleteData);

// Update device details
router.patch('/:deviceName', /* apiKeyAuth, */ updateDevice);

module.exports = router;
