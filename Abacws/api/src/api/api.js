const cors = require('cors');
const express = require('express');
const { consoleLogErrors, errorHandler, mongodbLogErrors } = require('./middleware');
const { devices, docs, healthcheck, query, admin, datasources, mappings, latest, rules, stream, debug } = require('./routers');

/** Express app */
const api = express();
// Api will only respond to JSON
api.use(cors());
api.use(express.json());

// Health now handled at top-level app (/health & /health/db). Keep optional legacy route.
api.get('/health', (_req, res) => res.status(200).json({ status: 'ok', note: 'See top-level /health for db status' }));

// Register routes
api.use("/healthcheck", healthcheck);
api.use("/query", query);
api.use("/devices", devices);
api.use("/admin", admin);
api.use("/datasources", datasources);
api.use("/mappings", mappings);
api.use("/latest", latest);
api.use('/rules', rules);
api.use('/stream', stream);
api.use('/debug', debug);

// Register error handlers
api.use(mongodbLogErrors);
api.use(consoleLogErrors);
api.use(errorHandler);

// Register documentation router
api.use("/", docs);

module.exports = api;
