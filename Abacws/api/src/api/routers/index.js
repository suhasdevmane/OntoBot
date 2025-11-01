const { DB_ENGINE } = require('../constants');
const express = require('express');
const base = { docs: require('./docs') };

if (DB_ENGINE === 'postgres') {
  // Provide lightweight stubs for Mongo-backed routers
  const okRouter = () => { const r = express.Router(); r.get('/', (_req,res)=>res.json({ ok: true })); return r; };
  base.healthcheck = okRouter();
  base.query = okRouter();
  base.admin = okRouter();
  base.devices = require('./devices');
  base.datasources = require('./datasources');
  base.mappings = require('./mappings');
  base.latest = require('./latest');
  base.stream = require('./stream');
  base.rules = require('./rules');
  base.debug = require('./debug');
} else {
  base.healthcheck = require('./healthcheck');
  base.devices = require('./devices');
  base.query = require('./query');
  base.admin = require('./admin').router;
  base.datasources = require('./datasources');
  base.mappings = require('./mappings');
  base.latest = require('./latest');
  base.stream = require('./stream');
  base.rules = require('./rules');
  base.debug = require('./debug');
}

module.exports = base;
