const express = require('express');
const store = require('../datastore');
const { apiKeyAuth } = require('../middleware');

const router = express.Router();

function ensureSupported(res) {
  // Allow both Postgres and MySQL engines for data sources
  if (store.engine !== 'postgres' && store.engine !== 'mysql') {
    res.status(501).json({ error: 'Data sources not supported for this engine' });
    return false;
  }
  return true;
}

router.get('/', async (_req, res, next) => {
  try { if (!ensureSupported(res)) return; const list = await store.listDataSources(); res.json(list); } catch(e){ next(e);} });
router.post('/', apiKeyAuth, async (req, res, next) => {
  try { if (!ensureSupported(res)) return; const created = await store.createDataSource(req.body||{}); res.status(201).json(created);} catch(e){ next(e);} });
router.patch('/:id', apiKeyAuth, async (req, res, next) => {
  try { if (!ensureSupported(res)) return; const updated = await store.updateDataSource(Number(req.params.id), req.body||{}); if(!updated) return res.status(404).json({error:'Not found'}); res.json(updated);} catch(e){ next(e);} });
router.delete('/:id', apiKeyAuth, async (req, res, next) => {
  try { if (!ensureSupported(res)) return; const out = await store.deleteDataSource(Number(req.params.id)); if(out.error) return res.status(400).json({error: out.error}); res.json({ ok: true }); } catch(e){ next(e);} });

// Introspection
router.get('/:id/tables', async (req, res, next) => {
  try { if (!ensureSupported(res)) return; const tables = await store.listTablesForDataSource(Number(req.params.id)); if (tables===null) return res.status(404).json({error:'Not found'}); res.json(tables);} catch(e){ next(e);} });
router.get('/:id/columns', async (req, res, next) => {
  try { if (!ensureSupported(res)) return; const table = req.query.table; if(!table) return res.status(400).json({error:'Missing table parameter'}); const cols = await store.listColumnsForDataSourceTable(Number(req.params.id), String(table)); if(cols===null) return res.status(404).json({error:'Not found'}); res.json(cols);} catch(e){ next(e);} });

module.exports = router;