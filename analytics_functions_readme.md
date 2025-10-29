# Analytics Functions: Input, Defaults, and Outputs

This guide documents every analytics function implemented in `functions.txt`: input format, default setpoints/thresholds, parameters, expected outputs, units, and notes.

## Input format

All functions accept a single top-level argument `sensor_data` that is a JSON-like Python dict. Two shapes are supported:

- Nested (grouped) shape:

  {
    "1": {
      "Zone1_CO2": { "timeseries_data": [ {"datetime": "2025-01-01 00:00:00", "reading_value": 800.0}, ... ] },
      "Zone1_Temperature": { "timeseries_data": [ {"datetime": "2025-01-01 00:00:00", "reading_value": 22.1}, ... ] }
    },
    "2": { ... }
  }

- Flat shape:

  {
    "Zone1_CO2": [ {"timestamp": "2025-01-01T00:00:00Z", "reading_value": 800.0}, ... ],
    "OAT_Temperature": [ {"timestamp": "2025-01-01T00:00:00Z", "reading_value": 12.3}, ... ]
  }

Notes
- Reading objects should include `reading_value` (number) and either `datetime` or `timestamp` (ISO-8601 string). Extra fields are ignored.
- Keys are matched using flexible name predicates (e.g., "outside_air" ≈ "outdoor", "supply_air", "return_air", etc.).
- Time alignment uses nearest-merge with ~5 minute tolerance and resampling at 1, 5, 15, or 60 minutes as needed per function. Missing values are handled robustly.
- Units are assumed as commonly used in HVAC unless stated otherwise (see below). Provide consistent units for best results.

## Common units and conventions

- Temperature: °C
- Relative humidity: %
- CO2: ppm
- TVOC, PM2.5/PM10: µg/m³
- Pressure: Pa (static), kPa for atmospheric
- Airflow: m³/s
- Water flow: typically m³/s or L/s (functions treat numerically; ensure consistency)
- Electric power: kW; Energy: kWh (cumulative when present)
- Illuminance: lux; Noise: dBA
- Valve/damper positions: %

Resampling and alignment
- Resampling intervals used: 1 min, 5 min, 15 min, or 60 min depending on the metric
- Merge tolerance: ±5 minutes for series alignment
- Daily aggregations use calendar-day grouping by timestamp date

## Default setpoints and thresholds

Many functions include sensible defaults. You can override via parameters.

- CO2 threshold: 1000 ppm
- TVOC threshold: 500 µg/m³
- Ammonia (NH3) threshold: 25 ppm
- PM thresholds: PM2.5=35 µg/m³; PM10=50 µg/m³; PM1=50 µg/m³ (proxy)
- IAQ composite thresholds: pm2.5 35; pm10 50; NO2 40 (µg/m³); CO 9 (ppm); CO2 1000 (ppm)
- Temperature comfort range: from `UK_INDOOR_STANDARDS["temperature_c"]["range"]` if available (commonly 20–24 °C); override in function params
- RH comfort range: from `UK_INDOOR_STANDARDS["humidity_rh"]["range"]` if available (commonly 30–60 %RH)
- CO safety: 30 ppm; CO2 safety: 5000 ppm
- Economizer opportunity: OAT at least 1.0 °C below RAT (dry-bulb method)
- Economizer damper open threshold: 30 %
- Low chilled-water ΔT flags: below 3 °C (primary), below 5 °C (secondary)
- Supply static pressure target: inferred as the series median if not provided
- Setpoint compliance tolerance: ±1.0 °C (or value units)
- Filter ΔP change indicator: current ΔP > 1.5 × mean ΔP
- Frost risk OAT threshold: ≤ 0.0 °C
- DR shed fraction estimate: 15 % of peak kW
- Part-load low threshold: PLR < 0.3
- Fan SFP bands: good < 1.5; ok < 2.5; else poor
- Pump SPP high flag: > 2.5
- Illuminance band around target: ±100 lux
- Noise comfort/high: 55 / 70 dBA
- Occupancy inference: occupied if CO2 > baseline + 150 ppm and 5‑min rise > 20 ppm
- Per-person ventilation guideline: 10 L/s per person; min occupancy clamp = 1 person
- Degree-day base temperature: 18 °C

If `UK_INDOOR_STANDARDS` isn’t defined at runtime, range-based functions return notes requesting explicit ranges in their parameters.

## Function catalog

Each entry lists: description; required signals; parameters (with defaults); returns; units; and notes.

1) analyze_tvoc_levels(sensor_data, threshold=500.0)
- Description: TVOC stats across all TVOC-like keys with alert vs threshold.
- Requires: any key containing "tvoc" or "voc".
- Returns: mean, min, max, std, latest, acceptable_max, alert, unit=µg/m³.

2) analyze_ammonia_levels(sensor_data, threshold=25.0)
- Description: Ammonia (NH3) stats with alert vs threshold.
- Requires: keys like "ammonia", "nh3".
- Returns: mean, min, max, std, latest, acceptable_max, alert, unit=ppm.

3) analyze_missing_data_scan(sensor_data, expected_freq=None)
- Description: Coverage and gap analysis per series.
- Parameters: expected_freq (e.g., "5min") for strict coverage.
- Returns: per-key coverage_pct, points, null_count, longest_gap_seconds, top_gaps.

4) analyze_flatline_detector(sensor_data, min_duration_points=5)
- Description: Detects flatline runs in each signal.
- Returns: per-key flatline_periods, count, severity.

5) analyze_spike_outliers(sensor_data, method="iqr", threshold=1.5, robust=True)
- Description: Spike/outlier detection using IQR or robust z.
- Returns: per-key list of anomalies with timestamp, reading_value, score.

6) analyze_sensor_drift_bias(sensor_data)
- Description: Pairwise drift (per day) and bias between sensor pairs.
- Returns: mapping "A__vs__B" to drift_per_day, bias_mean, confidence.

7) analyze_range_validation(sensor_data, ranges=None)
- Description: Validates readings against min/max ranges.
- Defaults: infers from UK_INDOOR_STANDARDS by key type if available.
- Returns: per-key percent_in_range, violations list, range used.

8) analyze_timestamp_consistency(sensor_data)
- Description: Duplicate timestamps and strictly-increasing check.
- Returns: per-key duplicates count, strictly_increasing flag.

9) analyze_pm_levels(sensor_data, thresholds={pm1:50, pm2.5:35, pm10:50})
- Description: PM1/PM2.5/PM10 stats and alert vs threshold.
- Returns: for each detected PM type: stats, latest, unit, threshold if provided.

10) analyze_iaq_composite(sensor_data)
- Description: IAQ score from pollutants using weighted thresholds.
- Returns: IAQ score, status label, component contributions, units map.

11) analyze_humidity_profile(sensor_data, acceptable_range=UK standard)
- Description: RH comfort profile (time-in-range, high/low counts).
- Returns: mean, min, max, latest, acceptable_range, time_in_range_pct, high_rh_count, low_rh_count, alert.

12) analyze_dewpoint_tracking(sensor_data)
- Description: Dewpoint from T and RH with condensation risk heuristic.
- Requires: temperature-like and RH-like series.
- Returns: dewpoint_latest, dewpoint_mean, unit=°C, risk.

13) analyze_air_enthalpy_grains(sensor_data, pressure_kpa=101.325)
- Description: Air enthalpy (kJ/kg dry air) and humidity ratio (grains/lb).
- Requires: temperature and RH.
- Returns: enthalpy_mean/latest, grains_mean/latest, units, notes.

14) analyze_zone_iaq_compliance(sensor_data, co2_max=None, rh_range=None)
- Description: % time within CO2 and RH limits (site-level proxy).
- Defaults: CO2 max and RH range from UK_INDOOR_STANDARDS.
- Returns: {site: {co2_compliance_pct, rh_compliance_pct, latest_co2, latest_rh}}.

15) analyze_iaq_contrast_outdoor_indoor(sensor_data, threshold_ppm=100)
- Description: OA vs RA CO2 differential; economizer feasibility flag.
- Returns: differential_latest, opportunity bool, approx_opportunity_count.

16) analyze_zone_temperature_summary(sensor_data, comfort_range=UK standard)
- Description: Zone temperature stats and time-in-comfort.
- Returns: mean/min/max/latest, unit=°C, time_in_comfort_pct, acceptable_range.

17) analyze_simple_comfort_index(sensor_data, t_target=22.0, rh_target=50.0)
- Description: Heuristic comfort score 0–100 from T and RH deviation.
- Returns: score_latest, score_mean, notes.

18) analyze_pmv_ppd_approximation(sensor_data, clo=0.5, met=1.1, air_speed=0.1, tr=None)
- Description: Approximate PMV/PPD from simplified inputs.
- Returns: pmv_latest, ppd_latest, assumptions.

19) analyze_temperature_setpoint_tracking(sensor_data, setpoint_keys=None)
- Description: Actual vs setpoint tracking.
- Returns: mae, overshoot_count, undershoot_count, within_band_pct (±0.5°C band).

20) analyze_setpoint_deviation(sensor_data, tolerance=1.0)
- Description: % time beyond tolerance between actual and setpoint.
- Returns: percent_beyond_tolerance, avg_deviation, tolerance.

21) analyze_mixed_air_validation(sensor_data)
- Description: MAT plausibility: OAT ≤ MAT ≤ RAT (cooling case) and residuals.
- Returns: violations_count, residual_mean.

22) analyze_economizer_opportunity(sensor_data, method="drybulb", delta=1.0)
- Description: Free cooling opportunities when OAT sufficiently below RAT.
- Returns: opportunity_count, latest_flag.

23) analyze_supply_air_temp_control(sensor_data)
- Description: SAT stability via variance and difference zero-crossings.
- Returns: variance, stability_flag.

24) analyze_supply_static_pressure_control(sensor_data, target=None)
- Description: Static pressure MAE vs target and oscillation index.
- Defaults: target inferred as median if not provided.
- Returns: mae, oscillation_index, target.

25) analyze_airflow_profiling(sensor_data)
- Description: Supply/return/mixed airflow averages, balance ratio, leakage hint.
- Returns: supply_avg, return_avg, mixed_avg, balance_ratio, leakage_hint.

26) analyze_filter_health(sensor_data, delta_p_threshold=None)
- Description: Filter ΔP health; normalized by airflow if present.
- Defaults: alert if latest ΔP > 1.5× mean ΔP.
- Returns: dp_latest, dp_mean, normalized_dp, unit=Pa, alert.

27) analyze_damper_performance(sensor_data, flatline_points=10)
- Description: Damper variance, flatline detections, stuck flag.
- Returns: variance, flatline_count, stuck_flag.

28) analyze_coil_delta_t_effectiveness(sensor_data)
- Description: Coil ΔT mean/latest and effectiveness proxy.
- Returns: delta_t_mean, delta_t_latest, effectiveness_proxy, unit=°C.

29) analyze_frost_freeze_risk(sensor_data, oat_threshold=0.0)
- Description: Frost sensor (if any) or OAT ≤ threshold risk events.
- Returns: risk_events, latest_flag.

30) analyze_return_mixed_outdoor_consistency(sensor_data)
- Description: Violations of RAT ≥ MAT ≥ OAT ordering.
- Returns: violation_count.

31) analyze_chilled_water_delta_t(sensor_data)
- Description: CHW ΔT = Return − Supply and low-ΔT flag.
- Returns: delta_t_mean, delta_t_latest, low_delta_t_flag, unit=°C.

32) analyze_chilled_water_flow_health(sensor_data)
- Description: CHW flow min/avg/max and low flow flag.
- Returns: min_flow, avg_flow, max_flow, low_flow_flag.

33) analyze_loop_differential_pressure(sensor_data, loop="chw", target=None)
- Description: Loop DP mean and MAE to target if provided.
- Returns: dp_mean, mae_to_target, target (if provided).

34) analyze_coil_valve_diagnostics(sensor_data)
- Description: Valve leakage/stiction heuristics from position, temps, flow.
- Returns: leakage_suspicion, stiction_suspicion, notes.

35) analyze_heat_exchanger_effectiveness(sensor_data)
- Description: HX effectiveness from hot/cold in/out temperatures.
- Returns: effectiveness [0–1], notes.

36) analyze_condenser_loop_health(sensor_data)
- Description: Condenser loop temp/flow means and approach proxy.
- Returns: temp_mean, flow_mean, approach_proxy.

37) analyze_electric_power_summary(sensor_data)
- Description: Total kW profile summary and integrated kWh.
- Returns: avg_kW, peak_kW, peak_time, total_kWh, period_start, period_end, interval.

38) analyze_load_profile(sensor_data)
- Description: Diurnal (hourly) and weekly load profiles.
- Returns: hourly_mean_kW[24], hourly_norm[24], weekday_kWh[0..6].

39) analyze_demand_response_readiness(sensor_data, shed_fraction=0.15)
- Description: Heuristic shedable kW and ramp-down readiness score.
- Returns: peak_kW, shedable_kW, readiness_score.

40) analyze_part_load_ratio(sensor_data, equipment_hint=None)
- Description: PLR from kW vs near-peak or from command proxies.
- Returns: mean_plr, low_load_pct.

41) analyze_cooling_cop(sensor_data)
- Description: COP proxy from CHW flow × ΔT vs chiller kW.
- Returns: cop_proxy_mean, cop_proxy_latest, notes.

42) analyze_eer_seer(sensor_data)
- Description: EER≈3.412×COP proxy; SEER proxy as median EER.
- Returns: eer_median, seer_proxy.

43) analyze_eui(sensor_data, area_m2)
- Description: Site Energy Use Intensity (kWh/m²·yr).
- Requires: area_m2 > 0.
- Returns: eui_kwh_per_m2_yr, total_kWh, days_covered.

44) analyze_fan_vfd_efficiency(sensor_data)
- Description: Specific Fan Power (kW per airflow) with efficiency band.
- Returns: sfp_mean, band.

45) analyze_pump_efficiency(sensor_data)
- Description: Specific Pump Power (kW per flow) with high flag.
- Returns: spp_mean, high_flag.

46) analyze_runtime_analysis(sensor_data, use_power_threshold=True)
- Description: Runtime hours and duty cycle from status or power.
- Returns: runtime_hours, duty_cycle, threshold (if power-based).

47) analyze_schedule_compliance(sensor_data, schedule=None)
- Description: Runtime outside schedule; infers schedule if not supplied.
- Returns: outside_runtime_hours, inferred.

48) analyze_equipment_cycling_health(sensor_data)
- Description: Cycles/hour and short-cycle flag.
- Returns: cycles_per_hour, short_cycle_flag.

49) analyze_alarm_event_summary(sensor_data)
- Description: Alarm/event counts by type and MTBF approximation.
- Returns: total_events, by_type, mtbf_hours.

50) analyze_sensor_correlation_map(sensor_data, max_sensors=20)
- Description: Correlation matrix across up to N numeric signals.
- Returns: sensors (names), corr (matrix of floats).

51) analyze_lead_lag(sensor_data)
- Description: Cross-correlation lag and magnitude between two most variant signals.
- Returns: signal_a, signal_b, lag_minutes, corr_at_lag.

52) analyze_weather_normalization(sensor_data, base_temp_c=18.0)
- Description: kWh per CDD/HDD using OAT and power.
- Returns: kWh_per_CDD, kWh_per_HDD, days.

53) analyze_change_point_detection(sensor_data)
- Description: Daily regime shifts via rolling z-score.
- Returns: change_points (timestamps).

54) analyze_short_horizon_forecasting(sensor_data, horizon_steps=12)
- Description: Persistence+drift forecast with uncertainty bands (5‑min steps).
- Returns: forecast, lower, upper, step_minutes.

55) analyze_anomaly_detection_statistical(sensor_data, z_thresh=3.5)
- Description: Robust-z anomaly counts per series with example timestamps.
- Returns: totals {sensor:count}, examples {sensor:[timestamps]}.

56) analyze_ach(sensor_data, zone_volume_m3)
- Description: Air Changes per Hour from airflow and zone volume.
- Requires: zone_volume_m3 > 0.
- Returns: ach_mean, ach_latest, flag (low ACH if mean < 3).

57) analyze_ventilation_effectiveness(sensor_data, co2_threshold=1000)
- Description: % time CO2 below threshold and exceedance metrics.
- Returns: pct_below_threshold, max_exceedance, hours_above.

58) analyze_outdoor_air_fraction(sensor_data)
- Description: Realized OA fraction via temperatures: f_OA=(MAT−RAT)/(OAT−RAT).
- Returns: mean_fraction, latest_fraction.

59) analyze_setpoint_compliance(sensor_data, tolerance=1.0)
- Description: MAE/MAPE and % within tolerance band.
- Returns: mae, mape, pct_within, tolerance.

60) analyze_hunting_oscillation(sensor_data)
- Description: Oscillation frequency (cycles/hour) and amplitude index.
- Returns: frequency_cph, amplitude, index.

61) analyze_actuator_stiction(sensor_data, flatline_points=10)
- Description: Stiction index from flatlines and low motion.
- Returns: stiction_index, flatline_events, low_motion_pct, flag.

62) analyze_co_co2_safety(sensor_data, co_threshold=30.0, co2_threshold=5000.0)
- Description: CO and CO2 safety metrics including 8h TWA max.
- Returns: CO:{peak,hours_above,twa8_max,threshold,severity}, CO2:{...}.

63) analyze_illuminance_luminance_tracking(sensor_data, target_lux=None, band=100.0)
- Description: Light level tracking vs target.
- Returns: mean_lux, median_lux, mae_to_target, pct_within_band, target_lux, band.

64) analyze_noise_monitoring(sensor_data, comfort_threshold=55.0, high_threshold=70.0)
- Description: Acoustic comfort percentiles and exceedances.
- Returns: p50, p90, max, pct_above_comfort, pct_above_high.

65) analyze_sensor_swap_bias_inference(sensor_data)
- Description: Heuristics for swapped sensors and bias candidates.
- Returns: swap_suspicions [A<->B], bias_candidates [{sensor,bias}].

66) analyze_economizer_fault_rules(sensor_data, damper_open_thresh=30.0)
- Description: Rule-based economizer faults using OAT/RAT/MAT and damper.
- Returns: does_not_open_count, stuck_open_count, suggestions.

67) analyze_low_delta_t_syndrome(sensor_data)
- Description: CHW low-ΔT syndrome focused metrics.
- Returns: pct_below_3C, pct_below_5C, hours_low_dt, syndrome_flag.

68) analyze_simultaneous_heating_cooling(sensor_data)
- Description: Overlap of heating and cooling valve/command >10%.
- Returns: overlap_pct, overlap_hours.

69) analyze_benchmarking_dashboard(sensor_data, area_m2=None)
- Description: Compact KPIs for energy, comfort, ventilation.
- Returns: {energy, comfort, ventilation} bundles.

70) analyze_control_loop_auto_tuning_aid(sensor_data)
- Description: PID starting ranges from oscillation frequency and index.
- Returns: suggested_kp, suggested_ti_hours, suggested_td_hours, notes.

71) analyze_residual_based_coil_fdd(sensor_data)
- Description: Residuals of ΔT vs valve position regression for fouling.
- Returns: residual_mean, residual_std, fouling_flag, notes.

72) analyze_occupancy_inference_co2(sensor_data, baseline_window_hours=24)
- Description: CO2 baseline, rise events, occupancy fraction.
- Returns: baseline_ppm, events, occupancy_fraction.

73) analyze_co2_levels(sensor_data, threshold=1000)
- Description: CO2 stats and exceedance time vs threshold.
- Returns: mean, p95, max, pct_above, hours_above, latest, threshold, unit.

74) analyze_per_person_ventilation_rate(sensor_data, guideline_lps=10.0, min_occ=1)
- Description: L/s per person from airflow and occupancy.
- Returns: mean_lps_per_person, p10_lps_per_person, pct_meeting_guideline, guideline_lps.

75) analyze_baseline_energy_regression(sensor_data, base_temp_c=18.0)
- Description: Daily kWh ~ CDD + HDD + intercept; coefficients and R².
- Returns: intercept, beta_cdd, beta_hdd, r2, days.

76) analyze_load_zone_clustering(sensor_data, n_clusters=3, resample="1H")
- Description: Zone clustering by normalized 24-hour profiles.
- Returns: clusters {zone:cluster_id}, centroids [[24]], inertia.

77) analyze_predictive_maintenance_fans_pumps(sensor_data)
- Description: PdM health score/RUL using SFP, vibration, temperature, alarms, runtime.
- Returns: health_score, rul_days, factors.

78) analyze_predictive_maintenance_chillers_ahus(sensor_data)
- Description: PdM health score/RUL using COP, low-ΔT, economizer faults, alarms, runtime.
- Returns: health_score, rul_days, factors.

79) analyze_dr_event_impact_analysis(sensor_data, events)
- Description: DR shed/rebound for given event windows.
- Parameters: events = [{start,end}] ISO8601.
- Returns: events [{start,end,shed_kWh,rebound_kWh}], total_shed_kWh, total_rebound_kWh.

80) analyze_digital_twin_simulation(sensor_data, scenario=None)
- Description: What‑if: kWh delta from OAT shift and setpoint offset.
- Parameters: scenario {oat_delta, setpoint_offset}.
- Returns: delta_kWh, details {slope_kW_per_C, oat_delta, setpoint_offset}.

81) analyze_mpc_readiness_shadow_mode(sensor_data)
- Description: Shadow-mode improvement if available; otherwise heuristic readiness.
- Returns: method (shadow|heuristic), improvement_pct or readiness_score.

82) analyze_fault_signature_library_matching(sensor_data)
- Description: Matches diagnostics to common fault signatures.
- Returns: matches [{name, confidence, details}].

83) analyze_sat_residual_analysis(sensor_data)
- Description: SAT residuals vs expected mixing estimate (RAT/OAT).
- Returns: residual_mean, residual_std, high_residual_pct.

84) analyze_weather_normalized_benchmarking(sensor_data, area_m2=None)
- Description: Climate-normalized KPIs and composite score.
- Returns: eui_kwh_per_m2_yr, kWh_per_CDD, kWh_per_HDD, score.

## Usage tips

- Provide clean, consistent units; these functions don’t perform unit conversion.
- When multiple sensors exist per type, functions aggregate or pair-match using nearest-time merges.
- If alignment fails (e.g., too sparse/time-skewed data), functions return an `{"error": ...}` payload instead of raising.
- Many functions accept parameters to override defaults. Prefer passing explicit thresholds where site standards differ from the defaults above.

## Example call pattern (Python)

from functions import analyze_co2_levels

result = analyze_co2_levels(sensor_data, threshold=900)

if "error" in result:
    print("Analysis failed:", result["error"])
else:
    print(result)


That’s it—this README mirrors the current implementation in `functions.txt`. If you add/edit functions, please update this document to keep it in sync.
