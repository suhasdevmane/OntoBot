const express = require('express');
const store = require('../datastore');

const router = express.Router();

// Inspect external MySQL telemetry wiring for a device
router.get('/external/:deviceName', async (req, res) => {
  try {
    if (store.engine !== 'mysql' || typeof store.debugExternalSnapshot !== 'function') {
      return res.status(400).json({ error: 'External MySQL engine not active' });
    }
    const name = String(req.params.deviceName);
    const out = await store.debugExternalSnapshot(name);
    return res.status(200).json(out);
  } catch (e) {
    return res.status(500).json({ error: e.message });
  }
});

// Inspect external MySQL telemetry history for a device
router.get('/external/:deviceName/history', async (req, res) => {
  try {
    if (store.engine !== 'mysql' || typeof store.debugExternalHistory !== 'function') {
      return res.status(400).json({ error: 'External MySQL engine not active' });
    }
    const name = String(req.params.deviceName);
    const from = Number(req.query.from) || 0;
    const to = Number(req.query.to) || Date.now();
    const limit = Number(req.query.limit) || 5;
    const out = await store.debugExternalHistory(name, from, to, limit);
    return res.status(200).json(out);
  } catch (e) {
    return res.status(500).json({ error: e.message });
  }
});

module.exports = router;
