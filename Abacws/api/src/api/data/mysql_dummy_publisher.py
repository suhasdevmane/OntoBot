#!/usr/bin/env python3
"""
Continuous MySQL dummy data publisher for sensordb.sensor_data
- Inserts indefinitely until interrupted (Ctrl+C or SIGTERM)
- Graceful shutdown and resource cleanup
- Optional batching (executemany) for higher throughput
- Exponential backoff on transient failures
Requires: pip install PyMySQL
"""
from __future__ import annotations
import os
import random
import re
import sys
import time
import signal
from typing import Dict, List, Optional, Tuple

try:
    import pymysql
except Exception:
    print("PyMySQL is required. Install it with: pip install PyMySQL", file=sys.stderr)
    raise

# ============================ SETTINGS (edit me) ============================
SETTINGS = {
    # Connection
    'HOST': 'localhost',
    'PORT': 3307,
    'USER': 'root',
    'PASSWORD': 'mysql',
    'DB': 'sensordb',
    'TABLE': 'sensor_data',

    # Timestamp column: leave empty to auto-detect first TIMESTAMP/DATETIME
    'TIMESTAMP_COLUMN': 'Datetime',

    # Loop cadence
    'INTERVAL_SECONDS': 10,     # delay between insert ticks

    # Batching: when >1 uses executemany per tick
    'BATCH_SIZE': 1,            # set to e.g. 50 for batch mode

    # Limits: set to 0 to run forever (recommended)
    'MAX_ROWS': 0,              # 0 = no limit, otherwise stop after N inserted rows

    # Logging
    'VERBOSE': True,

    # Backoff on errors
    'BACKOFF_INITIAL_S': 1.0,   # initial backoff
    'BACKOFF_FACTOR': 2.0,      # multiplier per failure
    'BACKOFF_MAX_S': 30.0,      # cap
}
# ===========================================================================

# Shutdown flag (set by signal handlers)
_SHOULD_STOP = False

def _signal_handler(sig, frame):
    global _SHOULD_STOP
    _SHOULD_STOP = True
    # Second signal forces immediate exit
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    signal.signal(signal.SIGTERM, signal.SIG_DFL)
    print("[py-dummy] Stop requested; finishing current tick and shutting down ...", flush=True)

def register_signal_handlers():
    # Handle Ctrl+C and SIGTERM for graceful shutdown
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

def pick(seq):
    return random.choice(seq)

def rand_int(a: int, b: int) -> int:
    return random.randint(a, b)

def rand_float(a: float, b: float, decimals: int = 2) -> float:
    v = random.random() * (b - a) + a
    return round(v, decimals)

def parse_enum_options(column_type: str) -> Optional[List[str]]:
    m = re.match(r"^enum\((.*)\)$", column_type.strip(), re.IGNORECASE)
    if not m:
        return None
    inner = m.group(1)
    opts = []
    cur = ''
    in_quote = False
    i = 0
    while i < len(inner):
        ch = inner[i]
        if ch == "'":
            in_quote = not in_quote
        elif ch == ',' and not in_quote:
            opts.append(cur)
            cur = ''
            i += 1
            continue
        cur += ch
        i += 1
    if cur:
        opts.append(cur)
    cleaned = [s.strip().strip("'").replace("\\'", "'") for s in opts]
    return cleaned

def connect_mysql(cfg) -> pymysql.connections.Connection:
    return pymysql.connect(
        host=cfg['host'], port=cfg['port'], user=cfg['user'], password=cfg['password'], database=cfg['db'],
        autocommit=True, cursorclass=pymysql.cursors.DictCursor
    )

def load_columns(conn, cfg) -> Tuple[str, List[Dict[str, object]]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name AS cname,
                   data_type   AS dtype,
                   column_type AS ctype,
                   is_nullable AS isnull,
                   numeric_precision AS nprec,
                   numeric_scale     AS nscale
            FROM information_schema.columns
            WHERE table_schema=%s AND table_name=%s
            ORDER BY ordinal_position
            """,
            (cfg['db'], cfg['table'])
        )
        rows = cur.fetchall()
        if not rows:
            raise RuntimeError(f"Table {cfg['db']}.{cfg['table']} not found or has no columns")
    ts_col = (cfg.get('ts_col_override') or '').strip()
    if not ts_col:
        ts = next((r for r in rows if str(r['dtype']).lower() == 'timestamp'), None)
        if not ts:
            ts = next((r for r in rows if str(r['dtype']).lower() == 'datetime'), None)
        if not ts:
            ts = next((r for r in rows if 'time' in str(r['dtype']).lower()), None)
        if not ts:
            raise RuntimeError('No timestamp/datetime column detected; set TIMESTAMP_COLUMN in SETTINGS')
        ts_col = ts['cname']
    value_cols = [r for r in rows if r['cname'] != ts_col]
    return ts_col, value_cols

def gen_value(col: Dict[str, object]):
    dt = str(col['dtype']).lower()
    ctype = str(col['ctype']).lower()
    if dt == 'enum':
        opts = parse_enum_options(ctype) or []
        return pick(opts) if opts else None
    if dt == 'tinyint':
        return rand_int(0, 1)
    if dt == 'smallint':
        return rand_int(0, 2000)
    if dt in ('mediumint', 'int', 'integer'):
        return rand_int(0, 100000)
    if dt == 'bigint':
        return rand_int(0, 10000000)
    if dt in ('decimal', 'numeric'):
        try:
            scale = int(col.get('nscale') or 2)
            prec = int(col.get('nprec') or 10)
        except Exception:
            scale, prec = 2, 10
        max_val = (10 ** max(1, prec - scale)) - 1
        return rand_float(0, max(1, min(max_val, 10000)), min(6, scale or 2))
    if dt in ('float', 'double', 'real'):
        return rand_float(0, 1000, 3)
    if dt == 'bit':
        return rand_int(0, 1)
    if dt in ('varchar', 'char', 'text', 'tinytext', 'mediumtext', 'longtext'):
        return f"val_{rand_int(0, 99999)}"
    if dt in ('date', 'datetime', 'timestamp'):
        return None  # handled by NOW()
    isnull = str(col.get('isnull', '')).upper() == 'YES'
    return None if isnull else f"val_{rand_int(0, 9999)}"

def build_insert_sql(cfg, ts_col: str, cols: List[Dict[str, object]]):
    col_names = [ts_col] + [c['cname'] for c in cols]
    placeholders = ['NOW()'] + ['%s' for _ in cols]
    sql = (
        f"INSERT INTO `{cfg['db']}`.`{cfg['table']}` ("
        + ", ".join([f"`{n}`" for n in col_names])
        + ") VALUES ("
        + ", ".join(placeholders)
        + ")"
    )
    return sql

def make_row_values(cols: List[Dict[str, object]]):
    return [gen_value(c) for c in cols]

def insert_single(conn, sql: str, vals: List[object], verbose=False):
    with conn.cursor() as cur:
        cur.execute(sql, vals)
    if verbose:
        print("[py-dummy] Inserted 1 row", flush=True)

def insert_batch(conn, sql: str, rows: List[List[object]], verbose=False):
    # Temporarily disable autocommit for batch, then commit once
    prev_autocommit = conn.get_autocommit()
    try:
        conn.autocommit(False)
        with conn.cursor() as cur:
            cur.executemany(sql, rows)
        conn.commit()
    finally:
        conn.autocommit(prev_autocommit)
    if verbose:
        print(f"[py-dummy] Inserted batch of {len(rows)} rows", flush=True)

def main() -> int:
    cfg = {
        'host': SETTINGS['HOST'],
        'port': int(SETTINGS['PORT']),
        'user': SETTINGS['USER'],
        'password': SETTINGS['PASSWORD'],
        'db': SETTINGS['DB'],
        'table': SETTINGS['TABLE'],
        'ts_col_override': SETTINGS.get('TIMESTAMP_COLUMN') or '',
    }
    interval = max(0, int(SETTINGS.get('INTERVAL_SECONDS', 10)))
    verbose = bool(SETTINGS.get('VERBOSE', False))
    batch_size = max(1, int(SETTINGS.get('BATCH_SIZE', 1)))
    max_rows = int(SETTINGS.get('MAX_ROWS', 0))
    backoff = float(SETTINGS.get('BACKOFF_INITIAL_S', 1.0))
    backoff_factor = float(SETTINGS.get('BACKOFF_FACTOR', 2.0))
    backoff_cap = float(SETTINGS.get('BACKOFF_MAX_S', 30.0))

    register_signal_handlers()

    if verbose:
        print(f"[py-dummy] Connecting to MySQL {cfg['host']}:{cfg['port']} db={cfg['db']}", flush=True)

    conn = connect_mysql(cfg)

    try:
        ts_col, cols = load_columns(conn, cfg)
        cols = [c for c in cols if c and c.get('cname') is not None]
        sql = build_insert_sql(cfg, ts_col, cols)

        if verbose:
            mode = "batch" if batch_size > 1 else "single"
            limit = "infinite" if max_rows == 0 else str(max_rows)
            print(f"[py-dummy] Target: {cfg['db']}.{cfg['table']}, ts: {ts_col}, value cols: {len(cols)}", flush=True)
            print(f"[py-dummy] Mode={mode}, batch_size={batch_size}, interval={interval}s, max_rows={limit}", flush=True)

        total = 0
        while True:
            if _SHOULD_STOP:
                break

            try:
                if batch_size == 1:
                    vals = make_row_values(cols)
                    insert_single(conn, sql, vals, verbose=verbose)
                    total += 1
                else:
                    rows = [make_row_values(cols) for _ in range(batch_size)]
                    insert_batch(conn, sql, rows, verbose=verbose)
                    total += len(rows)

                # reset backoff after a successful tick
                backoff = float(SETTINGS.get('BACKOFF_INITIAL_S', 1.0))

                if max_rows and total >= max_rows:
                    break

                # Sleep only if we’re not stopping
                if interval > 0:
                    for _ in range(interval):
                        if _SHOULD_STOP:
                            break
                        time.sleep(1)
            except KeyboardInterrupt:
                # Redundant due to signal handler but keeps behavior consistent
                break
            except Exception as e:
                # Log and back off, then retry until stopped
                print(f"[py-dummy] Error during insert: {e}. Backing off {backoff:.1f}s", file=sys.stderr, flush=True)
                slept = 0.0
                while slept < backoff and not _SHOULD_STOP:
                    time.sleep(0.2)
                    slept += 0.2
                backoff = min(backoff * backoff_factor, backoff_cap)
                # On some network failures, reconnect
                try:
                    conn.ping(reconnect=True)
                except Exception:
                    try:
                        conn.close()
                    except Exception:
                        pass
                    conn = connect_mysql(cfg)

        if verbose:
            print(f"[py-dummy] Stopping. Inserted total {total} rows.", flush=True)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass

if __name__ == '__main__':
    raise SystemExit(main())
