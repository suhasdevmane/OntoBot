const express = require('express');
const store = require('../datastore');
const { apiKeyAuth, deviceMiddleware } = require('../middleware');

const router = express.Router();

function ensureSupported(res) {
  // Allow both Postgres and MySQL engines for mappings
  if (store.engine !== 'postgres' && store.engine !== 'mysql') {
    res.status(501).json({ error: 'Mappings not supported for this engine' });
    return false;
  }
  return true;
}

router.get('/', async (_req, res, next) => { try { if(!ensureSupported(res)) return; const list = await store.listDeviceMappings(); res.json(list); } catch(e){ next(e);} });
router.post('/', apiKeyAuth, async (req, res, next) => { try { if(!ensureSupported(res)) return; const body = req.body||{}; if(!body.device_name||!body.data_source_id||!body.table_name||!body.device_id_column||!body.device_identifier_value||!body.timestamp_column||!Array.isArray(body.value_columns)||!body.value_columns.length){ return res.status(400).json({error:'Missing required fields'});} const created = await store.createDeviceMapping(body); res.status(201).json(created);} catch(e){ if(e.code==='23505') return res.status(409).json({error:'Mapping already exists'}); next(e);} });
router.patch('/:id', apiKeyAuth, async (req, res, next) => { try { if(!ensureSupported(res)) return; const updated = await store.updateDeviceMapping(Number(req.params.id), req.body||{}); if(!updated) return res.status(404).json({error:'Not found'}); res.json(updated);} catch(e){ next(e);} });
router.delete('/:id', apiKeyAuth, async (req, res, next) => { try { if(!ensureSupported(res)) return; await store.deleteDeviceMapping(Number(req.params.id)); res.json({ok:true}); } catch(e){ next(e);} });

// Verification (dry-run) endpoint - does not create mapping
router.post('/verify', apiKeyAuth, async (req,res,next)=>{
  try {
    if(!ensureSupported(res)) return;
    const out = await store.verifyDeviceMapping(req.body||{});
    if(out.error) return res.status(400).json(out);
    res.json(out);
  } catch(e){ next(e); }
});

// Per-device timeseries (could also live in devices router, but keep here for clarity)
router.get('/device/:deviceName/timeseries', async (req, res, next) => {
  try {
    if(!ensureSupported(res)) return;
    const from = Number(req.query.from) || Date.now() - 3600_000; // default last hour
    const to = Number(req.query.to) || Date.now();
    const limit = Math.min(Number(req.query.limit)||2000, 10000);
    const out = await store.fetchDeviceTimeseries(String(req.params.deviceName), from, to, limit);
    res.json(out);
  } catch(e){ next(e);} });

module.exports = router;