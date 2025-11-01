#!/usr/bin/env node
/*
  MySQL dummy data publisher for pivoted sensordb.sensor_data
  - Discovers all columns in sensordb.sensor_data (except the timestamp column)
  - Generates type-appropriate dummy values for each column
  - Inserts a new row every INTERVAL_MS (default 10s) with NOW() as timestamp

  How to run (inside API container):
    docker compose -f docker-compose.bldg1.yml exec api sh -lc "node /api/src/api/data/mysql_dummy_publisher.js"

  Env vars (optional overrides):
    DS_HOST=mysqlserver
    DS_PORT=3306
    DS_USER=root
    DS_PASSWORD=mysql
    DS_DB=sensordb
    DS_TABLE=sensor_data
    TIMESTAMP_COLUMN=Datetime   # auto-detected if not provided
    INTERVAL_MS=10000
*/

const mysql = require('mysql2/promise');

const CFG = {
  host: process.env.DS_HOST || 'mysqlserver',
  port: Number(process.env.DS_PORT || 3306),
  user: process.env.DS_USER || 'root',
  password: process.env.DS_PASSWORD || 'mysql',
  db: process.env.DS_DB || 'sensordb',
  table: process.env.DS_TABLE || 'sensor_data',
  tsColOverride: process.env.TIMESTAMP_COLUMN || '',
  intervalMs: Number(process.env.INTERVAL_MS || 10000),
};

function randInt(min, max){ return Math.floor(Math.random()*(max-min+1))+min; }
function randFloat(min, max, decimals=2){ const v = Math.random()*(max-min)+min; return Number(v.toFixed(decimals)); }
function pick(arr){ return arr[Math.floor(Math.random()*arr.length)]; }
function randFromEnum(def){
  // def like: "enum('FreshAir','high','medium','low')"
  const m = def.match(/^enum\((.*)\)$/i);
  if(!m) return null;
  const inner = m[1];
  // Split respecting quotes
  const opts = [];
  let cur = '';
  let inQuote = false;
  for(let i=0;i<inner.length;i++){
    const ch = inner[i];
    if(ch === "'") inQuote = !inQuote;
    else if(ch === ',' && !inQuote){ opts.push(cur); cur=''; continue; }
    cur += ch;
  }
  if(cur.length) opts.push(cur);
  // Clean up quotes and escapes
  const cleaned = opts.map(s=> s.trim().replace(/^'/,'').replace(/'$/,'').replace(/\\'/g,"'"));
  return pick(cleaned);
}

async function loadColumns(conn){
  const [rowsRaw, fields] = await conn.query(
    'SELECT column_name AS cname, data_type AS dtype, column_type AS ctype, is_nullable AS isnull, numeric_precision AS nprec, numeric_scale AS nscale FROM information_schema.columns WHERE table_schema=? AND table_name=? ORDER BY ordinal_position',
    [CFG.db, CFG.table]
  );
  const rows = Array.isArray(rowsRaw) && rowsRaw.length && Array.isArray(rowsRaw[0]) && fields
    ? rowsRaw.map(arr => Object.fromEntries(fields.map((f, i) => [f.name, arr[i]])))
    : rowsRaw;
  if(!rows.length) throw new Error(`Table ${CFG.db}.${CFG.table} not found`);
  // Identify timestamp column
  let tsCol = CFG.tsColOverride;
  if(!tsCol){
    const ts = rows.find(r=> String(r.dtype).toLowerCase() === 'timestamp') || rows.find(r=> /time/i.test(String(r.dtype)));
    if(!ts){
      console.error('[dummy] Columns:', rows.map(r=> ({ name: r.cname, data_type: r.dtype, column_type: r.ctype })));
      throw new Error('No timestamp column detected; set TIMESTAMP_COLUMN env');
    }
    tsCol = ts.cname;
  }
  const cols = rows.filter(r=> r.cname !== tsCol);
  return { tsCol, cols };
}

function genValue(col){
  const dt = String(col.dtype).toLowerCase();
  const ct = String(col.ctype).toLowerCase();
  switch(dt){
    case 'enum': {
      // Use column_type to parse options
  const v = randFromEnum(col.ctype);
      return v === null ? null : v;
    }
    case 'tinyint':
      return randInt(0, 1); // boolean-ish
    case 'smallint':
      return randInt(0, 2000);
    case 'mediumint':
    case 'int':
    case 'integer':
      return randInt(0, 100000);
    case 'bigint':
      return randInt(0, 10000000);
    case 'decimal':
    case 'numeric': {
  const scale = col.nscale != null ? Number(col.nscale) : 2;
  const prec = col.nprec != null ? Number(col.nprec) : 10;
      const max = Math.pow(10, Math.max(1, prec - scale)) - 1;
      const v = randFloat(0, Math.max(1, Math.min(max, 10000)), Math.min(6, scale||2));
      return v;
    }
    case 'float':
    case 'double':
    case 'real':
      return randFloat(0, 1000, 3);
    case 'bit':
      return randInt(0, 1);
    case 'varchar':
    case 'char':
    case 'text':
    case 'tinytext':
    case 'mediumtext':
    case 'longtext':
      return `val_${randInt(0,99999)}`;
    case 'date':
    case 'datetime':
    case 'timestamp':
      return null; // handled as NOW() for the designated ts column only
    default:
      // For unknowns, try NULL if allowed else a string token
      if(String(col.isnull).toUpperCase() === 'YES') return null;
      return `val_${randInt(0,9999)}`;
  }
}

async function buildInsert(conn, tsCol, cols){
  // Build column list and values array. tsCol uses NOW() expression.
  const colNames = [tsCol, ...cols.map(c=> c.cname)];
  const placeholders = ['NOW()', ...cols.map(_=> '?')];
  const values = cols.map(c=> genValue(c));
  const sql = `INSERT INTO \`${CFG.db}\`.\`${CFG.table}\` (${colNames.map(n=> `\`${n}\``).join(', ')}) VALUES (${placeholders.join(', ')})`;
  return { sql, values };
}

async function main(){
  console.log(`[dummy] Connecting to MySQL ${CFG.host}:${CFG.port} db=${CFG.db}`);
  const pool = await mysql.createPool({ host: CFG.host, port: CFG.port, user: CFG.user, password: CFG.password, database: CFG.db, waitForConnections: true, connectionLimit: 5 });
  const conn = await pool.getConnection();
  try {
    let { tsCol, cols } = await loadColumns(conn);
  const before = cols.length;
  if(before){ console.log('[dummy] Column keys example:', Object.keys(cols[0]||{})); }
  const undefinedCount = cols.reduce((acc,c)=> acc + (c && c.cname!==undefined ? 0 : 1), 0);
  cols = cols.filter(c=> c && c.cname !== undefined);
    const filtered = before - cols.length;
  console.log(`[dummy] Target table: ${CFG.db}.${CFG.table}, timestamp column: ${tsCol}, value columns: ${cols.length}${filtered? ` (filtered ${filtered} invalid columns)`:''}`);

    const tick = async () => {
      try {
  const { sql, values } = await buildInsert(conn, tsCol, cols);
  if(/`undefined`/.test(sql)) throw new Error('Detected undefined column in SQL');
        await conn.query(sql, values);
        console.log(`[dummy] Inserted row at NOW() with ${values.length} values`);
      } catch(err){
        console.error('[dummy] Insert error:', err.message);
      }
    };

    // First insert immediately, then interval
    await tick();
    const handle = setInterval(tick, CFG.intervalMs);

    // Graceful shutdown
    process.on('SIGINT', async ()=>{ clearInterval(handle); await conn.release(); await pool.end(); process.exit(0); });
    process.on('SIGTERM', async ()=>{ clearInterval(handle); await conn.release(); await pool.end(); process.exit(0); });
  } catch(e){
    console.error('[dummy] Fatal:', e.message);
    try { await conn.release(); } catch(_){}
    try { await pool.end(); } catch(_){}
    process.exit(1);
  }
}

main();
