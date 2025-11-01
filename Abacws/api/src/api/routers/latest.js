const express = require('express');
const store = require('../datastore');

const router = express.Router();

function ensureSupported(res) {
  // Allow both Postgres and MySQL engines (both implement fetchLatestForAllMappings)
  if (store.engine !== 'postgres' && store.engine !== 'mysql') {
    res.status(501).json({ error: 'Latest endpoint not supported for this engine' });
    return false;
  }
  return true;
}

router.get('/', async (req, res, next) => {
  try {
    if(!ensureSupported(res)) return;
    // Default to a generous lookback to support historical datasets; cap to 10 years
    const days = Math.min(Number(req.query.lookbackDays)||3650, 3650);
    const data = await store.fetchLatestForAllMappings(days);
    res.json(data);
  } catch(e){ next(e); }
});

module.exports = router;