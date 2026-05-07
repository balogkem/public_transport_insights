from flask import Flask, jsonify, send_from_directory, request, Response
from flask_cors import CORS
from decimal import Decimal
import json as _json
import os
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from db import get_connection

app = Flask(
    __name__,
    static_folder="../frontend",
    static_url_path=""
)
CORS(app)


# ── safe JSON serialiser — works on all Flask versions ─────────
# app.json_encoder is deprecated/ignored in Flask 2.3+.
# This converts Decimal → float recursively before serialising.
def safe_jsonify(data):
    def _convert(obj):
        if isinstance(obj, Decimal): return float(obj)
        if isinstance(obj, dict):    return {k: _convert(v) for k, v in obj.items()}
        if isinstance(obj, list):    return [_convert(i) for i in obj]
        return obj
    return Response(_json.dumps(_convert(data)), mimetype="application/json")



# ── serve frontend ─────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory("../frontend", "index.html")


# ── helper ─────────────────────────────────────────────────────
def query_db(sql, params=()):
    conn = get_connection()
    if conn is None:
        return None
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        cols = [desc[0] for desc in cur.description]
        rows = []
        for row in cur.fetchall():
            d = {}
            for c, v in zip(cols, row):
                # coerce Decimal → float so JSON serialises cleanly
                d[c] = float(v) if isinstance(v, Decimal) else v
            rows.append(d)
        return rows
    except Exception as e:
        print(f"Query error: {e}")
        return None
    finally:
        conn.close()


# ── /api/status ────────────────────────────────────────────────
@app.route("/api/status")
def status():
    conn = get_connection()
    if conn is None:
        return jsonify({"connected": False, "message": "Database not connected."})
    conn.close()
    return jsonify({"connected": True, "message": "Connected to Supabase (PostgreSQL)"})


# ── /api/hero ──────────────────────────────────────────────────
@app.route("/api/hero")
def hero():
    rows = query_db("""
        SELECT
            (SELECT COUNT(*)                                FROM route)           AS total_routes,
            (SELECT COUNT(*)                                FROM trip)            AS total_trips,
            (SELECT ROUND(AVG(delay_mins)::numeric, 1)     FROM trip)            AS avg_delay,
            (SELECT ROUND(AVG(capacity_utilisation_pct)::numeric, 1)
             FROM passenger_record)                                               AS avg_capacity
    """)
    if rows is None:
        return jsonify({"error": "DB not connected"}), 503
    return safe_jsonify(rows[0])


# ── /api/routes/delays ─────────────────────────────────────────
# Q1: All routes ordered by avg delay. congestion_zone returned as int (0/1).
@app.route("/api/routes/delays")
def route_delays():
    rows = query_db("""
        SELECT
            r.route_name,
            r.start_borough,
            r.end_borough,
            r.passes_congestion_zone                        AS congestion_zone,
            ROUND(AVG(t.delay_mins)::numeric, 1)           AS avg_delay_mins,
            ROUND(MIN(t.delay_mins)::numeric, 1)           AS min_delay,
            ROUND(MAX(t.delay_mins)::numeric, 1)           AS max_delay,
            COUNT(t.trip_id)                               AS total_trips
        FROM trip t
        JOIN route r ON t.route_id = r.route_id
        GROUP BY r.route_name, r.start_borough, r.end_borough, r.passes_congestion_zone
        ORDER BY avg_delay_mins DESC
    """)
    if rows is None:
        return jsonify({"error": "DB not connected"}), 503
    return safe_jsonify(rows)


# ── /api/routes/delay-distribution ────────────────────────────
@app.route("/api/routes/delay-distribution")
def delay_distribution():
    rows = query_db("""
        SELECT bracket, COUNT(*) AS trip_count
        FROM (
            SELECT
                CASE
                    WHEN delay_mins < 3  THEN '0-3'
                    WHEN delay_mins < 6  THEN '3-6'
                    WHEN delay_mins < 9  THEN '6-9'
                    WHEN delay_mins < 12 THEN '9-12'
                    WHEN delay_mins < 16 THEN '12-16'
                    ELSE '16+'
                END AS bracket,
                CASE
                    WHEN delay_mins < 3  THEN 1
                    WHEN delay_mins < 6  THEN 2
                    WHEN delay_mins < 9  THEN 3
                    WHEN delay_mins < 12 THEN 4
                    WHEN delay_mins < 16 THEN 5
                    ELSE 6
                END AS sort_order
            FROM trip
        ) sub
        GROUP BY bracket, sort_order
        ORDER BY sort_order
    """)
    if rows is None:
        return jsonify({"error": "DB not connected"}), 503
    return safe_jsonify(rows)


# ── /api/routes/by-borough ─────────────────────────────────────
@app.route("/api/routes/by-borough")
def routes_by_borough():
    rows = query_db("""
        SELECT
            r.start_borough                                AS borough,
            ROUND(AVG(t.delay_mins)::numeric, 1)          AS avg_delay_mins,
            COUNT(t.trip_id)                              AS total_trips
        FROM trip t
        JOIN route r ON t.route_id = r.route_id
        GROUP BY r.start_borough
        ORDER BY avg_delay_mins DESC
    """)
    if rows is None:
        return jsonify({"error": "DB not connected"}), 503
    return safe_jsonify(rows)


# ── /api/routes/cz-comparison ──────────────────────────────────
# Extra query for the SQL queries panel — CZ vs non-CZ breakdown
@app.route("/api/routes/cz-comparison")
def cz_comparison():
    rows = query_db("""
        SELECT
            CASE WHEN r.passes_congestion_zone = 1
                 THEN 'Congestion Zone'
                 ELSE 'Non-Congestion Zone'
            END                                            AS zone_type,
            COUNT(DISTINCT r.route_id)                    AS route_count,
            ROUND(AVG(t.delay_mins)::numeric, 1)          AS avg_delay_mins,
            ROUND(MIN(t.delay_mins)::numeric, 1)          AS min_delay,
            ROUND(MAX(t.delay_mins)::numeric, 1)          AS max_delay,
            COUNT(t.trip_id)                              AS total_trips
        FROM trip t
        JOIN route r ON t.route_id = r.route_id
        GROUP BY r.passes_congestion_zone
        ORDER BY avg_delay_mins DESC
    """)
    if rows is None:
        return jsonify({"error": "DB not connected"}), 503
    return safe_jsonify(rows)


# ── /api/passengers/scatter ────────────────────────────────────
@app.route("/api/passengers/scatter")
def passengers_scatter():
    rows = query_db("""
        SELECT
            pr.capacity_utilisation_pct  AS capacity_pct,
            t.delay_mins                 AS delay_mins,
            pr.overcrowding_flag         AS overcrowded
        FROM trip t
        JOIN passenger_record pr ON t.trip_id = pr.trip_id
        ORDER BY RANDOM()
        LIMIT 500
    """)
    if rows is None:
        return jsonify({"error": "DB not connected"}), 503
    return safe_jsonify(rows)


# ── /api/passengers/overrun-by-bracket ────────────────────────
# FIX: ensure bracket labels exactly match what frontend expects.
@app.route("/api/passengers/overrun-by-bracket")
def overrun_by_bracket():
    rows = query_db("""
        SELECT
            CASE
                WHEN pr.capacity_utilisation_pct < 50 THEN '<50%'
                WHEN pr.capacity_utilisation_pct < 75 THEN '50-75%'
                WHEN pr.capacity_utilisation_pct < 90 THEN '75-90%'
                ELSE '>90%'
            END                                                           AS capacity_bracket,
            COUNT(*)                                                       AS trip_count,
            ROUND(AVG(t.actual_duration_mins - t.scheduled_duration_mins)
                  ::numeric, 1)                                            AS avg_overrun_mins,
            ROUND(AVG(pr.peak_count)::numeric, 0)                         AS avg_peak_passengers
        FROM trip t
        JOIN passenger_record pr ON t.trip_id = pr.trip_id
        GROUP BY capacity_bracket
        ORDER BY avg_overrun_mins DESC
    """)
    if rows is None:
        return jsonify({"error": "DB not connected"}), 503
    return safe_jsonify(rows)


# ── /api/passengers/peak-hours ─────────────────────────────────
@app.route("/api/passengers/peak-hours")
def peak_hours():
    rows = query_db("""
        SELECT
            EXTRACT(HOUR FROM t.scheduled_departure)::int  AS hour,
            COUNT(*)                                        AS overcrowded_trips
        FROM trip t
        JOIN passenger_record pr ON t.trip_id = pr.trip_id
        WHERE pr.overcrowding_flag = 1
        GROUP BY EXTRACT(HOUR FROM t.scheduled_departure)
        ORDER BY hour
    """)
    if rows is None:
        return jsonify({"error": "DB not connected"}), 503
    return safe_jsonify(rows)


# ── /api/weather/delays ────────────────────────────────────────
@app.route("/api/weather/delays")
def weather_delays():
    rows = query_db("""
        SELECT
            wc.condition_label,
            COUNT(t.trip_id)                              AS trip_count,
            ROUND(AVG(t.delay_mins)::numeric, 1)         AS avg_delay_mins,
            ROUND(AVG(wc.rainfall_mm)::numeric, 2)       AS avg_rainfall_mm,
            ROUND(AVG(wc.temperature_c)::numeric, 1)     AS avg_temp_c,
            ROUND(AVG(wc.visibility_level)::numeric, 1)  AS avg_visibility,
            ROUND(MIN(t.delay_mins)::numeric, 1)         AS min_delay,
            ROUND(MAX(t.delay_mins)::numeric, 1)         AS max_delay
        FROM trip t
        JOIN weather_condition wc ON t.weather_id = wc.weather_id
        GROUP BY wc.condition_label
        ORDER BY avg_delay_mins DESC
    """)
    if rows is None:
        return jsonify({"error": "DB not connected"}), 503
    return safe_jsonify(rows)


# ── /api/weather/rainfall-scatter ─────────────────────────────
@app.route("/api/weather/rainfall-scatter")
def rainfall_scatter():
    rows = query_db("""
        SELECT
            ROUND(wc.rainfall_mm::numeric, 0)        AS rainfall_mm,
            ROUND(AVG(t.delay_mins)::numeric, 1)     AS avg_delay
        FROM trip t
        JOIN weather_condition wc ON t.weather_id = wc.weather_id
        WHERE wc.rainfall_mm > 0
        GROUP BY ROUND(wc.rainfall_mm::numeric, 0)
        ORDER BY rainfall_mm
    """)
    if rows is None:
        return jsonify({"error": "DB not connected"}), 503
    return safe_jsonify(rows)


# ── /api/vehicles/summary ──────────────────────────────────────
@app.route("/api/vehicles/summary")
def vehicles_summary():
    rows = query_db("""
        SELECT
            v.vehicle_type,
            v.emission_standard,
            v.capacity,
            COUNT(t.trip_id)                                     AS total_trips,
            ROUND(AVG(t.delay_mins)::numeric, 1)                 AS avg_delay_mins,
            ROUND(AVG(pr.capacity_utilisation_pct)::numeric, 1)  AS avg_capacity_pct
        FROM trip t
        JOIN vehicle v ON t.vehicle_id = v.vehicle_id
        JOIN passenger_record pr ON t.trip_id = pr.trip_id
        GROUP BY v.vehicle_type, v.emission_standard, v.capacity
        ORDER BY avg_delay_mins DESC
    """)
    if rows is None:
        return jsonify({"error": "DB not connected"}), 503
    return safe_jsonify(rows)


# ── /api/borough/search ────────────────────────────────────────
# FIX: now joins through Stop table so ANY borough a route passes
# through is matched — not just start/end terminals.
@app.route("/api/borough/search")
def borough_search():
    borough = request.args.get("q", "").strip()
    if not borough:
        return jsonify({"error": "No borough provided"}), 400

    routes = query_db("""
        SELECT DISTINCT
            r.route_name,
            r.start_borough,
            r.end_borough,
            r.passes_congestion_zone                          AS congestion_zone,
            ROUND(AVG(t.delay_mins)::numeric, 1)             AS avg_delay_mins,
            COUNT(t.trip_id)                                 AS total_trips,
            ROUND(AVG(pr.capacity_utilisation_pct)::numeric, 1) AS avg_capacity_pct
        FROM trip t
        JOIN route r ON t.route_id = r.route_id
        JOIN passenger_record pr ON t.trip_id = pr.trip_id
        WHERE r.route_id IN (
            SELECT DISTINCT s.route_id
            FROM stop s
            WHERE LOWER(s.borough) = LOWER(%s)
        )
        GROUP BY r.route_name, r.start_borough, r.end_borough, r.passes_congestion_zone
        ORDER BY avg_delay_mins DESC
    """, (borough,))

    weather = query_db("""
        SELECT
            wc.condition_label,
            ROUND(AVG(t.delay_mins)::numeric, 1)  AS avg_delay_mins,
            COUNT(t.trip_id)                       AS trip_count
        FROM trip t
        JOIN route r ON t.route_id = r.route_id
        JOIN weather_condition wc ON t.weather_id = wc.weather_id
        WHERE r.route_id IN (
            SELECT DISTINCT s.route_id FROM stop s
            WHERE LOWER(s.borough) = LOWER(%s)
        )
        GROUP BY wc.condition_label
        ORDER BY avg_delay_mins DESC
    """, (borough,))

    peak = query_db("""
        SELECT
            EXTRACT(HOUR FROM t.scheduled_departure)::int AS hour,
            COUNT(*) AS overcrowded_trips
        FROM trip t
        JOIN route r ON t.route_id = r.route_id
        JOIN passenger_record pr ON t.trip_id = pr.trip_id
        WHERE pr.overcrowding_flag = 1
          AND r.route_id IN (
              SELECT DISTINCT s.route_id FROM stop s
              WHERE LOWER(s.borough) = LOWER(%s)
          )
        GROUP BY EXTRACT(HOUR FROM t.scheduled_departure)
        ORDER BY hour
    """, (borough,))

    if routes is None:
        return jsonify({"error": "DB not connected"}), 503

    return safe_jsonify({
        "borough": borough,
        "routes":  routes  or [],
        "weather": weather or [],
        "peak":    peak    or [],
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, port=port)