"""
Script to add @analytics_function decorators to all analytics functions.
This creates a mapping of function names to their decorator definitions.
"""

# Mapping of function names to their decorator configurations
FUNCTION_DECORATORS = {
    "analyze_recalibration_frequency": {
        "patterns": [
            r"recalibration.*frequency",
            r"calibration.*schedule",
            r"when.*recalibrate",
            r"recalibration.*interval",
            r"sensor.*calibration.*check"
        ],
        "description": "Analyzes sensor recalibration frequency based on variability (CV > 0.1 suggests frequent recalibration needed)"
    },
    "analyze_failure_trends": {
        "patterns": [
            r"failure.*trend",
            r"fault.*pattern",
            r"failure.*analysis",
            r"sensor.*failure.*history",
            r"equipment.*failure.*rate"
        ],
        "description": "Analyzes failure trends and patterns across sensors to identify deteriorating equipment"
    },
    "analyze_device_deviation": {
        "patterns": [
            r"device.*deviation",
            r"equipment.*variance",
            r"sensor.*drift",
            r"measurement.*deviation",
            r"device.*performance"
        ],
        "description": "Analyzes deviation of device readings from expected values or baselines"
    },
    "analyze_sensor_status": {
        "patterns": [
            r"sensor.*status",
            r"sensor.*health",
            r"sensor.*condition",
            r"are.*sensors.*working",
            r"sensor.*operational"
        ],
        "description": "Checks overall sensor status and operational health across all monitored sensors"
    },
    "analyze_air_quality_trends": {
        "patterns": [
            r"air.*quality.*trend",
            r"iaq.*trend",
            r"air.*quality.*over.*time",
            r"air.*quality.*pattern",
            r"indoor.*air.*quality.*history"
        ],
        "description": "Analyzes indoor air quality trends over time for specific sensors"
    },
    "analyze_hvac_anomalies": {
        "patterns": [
            r"hvac.*anomaly",
            r"hvac.*fault",
            r"hvac.*abnormal",
            r"hvac.*issue",
            r"hvac.*problem.*detection"
        ],
        "description": "Detects anomalies and faults in HVAC system performance and operation"
    },
    "analyze_supply_return_temp_difference": {
        "patterns": [
            r"supply.*return.*temp",
            r"delta.*t",
            r"temperature.*difference.*supply.*return",
            r"supply.*return.*differential",
            r"sat.*rat.*difference"
        ],
        "description": "Analyzes temperature difference between supply and return air for HVAC efficiency"
    },
    "analyze_air_flow_variation": {
        "patterns": [
            r"air.*flow.*variation",
            r"airflow.*fluctuation",
            r"cfm.*variability",
            r"air.*flow.*stability",
            r"ventilation.*variation"
        ],
        "description": "Analyzes variation and stability in air flow rates across ventilation system"
    },
    "analyze_pressure_trend": {
        "patterns": [
            r"pressure.*trend",
            r"static.*pressure.*pattern",
            r"differential.*pressure.*trend",
            r"pressure.*over.*time",
            r"pressure.*change"
        ],
        "description": "Analyzes pressure trends and patterns, checking against expected ranges"
    },
    "analyze_sensor_trend": {
        "patterns": [
            r"sensor.*trend",
            r"reading.*trend",
            r"data.*trend",
            r"measurement.*pattern",
            r"sensor.*over.*time"
        ],
        "description": "Analyzes general trend patterns in sensor readings over a time window"
    },
    "aggregate_sensor_data": {
        "patterns": [
            r"aggregate.*data",
            r"summarize.*readings",
            r"resample.*data",
            r"group.*by.*time",
            r"hourly.*average"
        ],
        "description": "Aggregates sensor data by time frequency (hourly, daily, etc.) with statistical summaries"
    },
    "correlate_sensors": {
        "patterns": [
            r"correlate.*sensors",
            r"correlation.*analysis",
            r"relationship.*between",
            r"sensor.*correlation",
            r"dependency.*analysis"
        ],
        "description": "Computes correlation matrix between multiple sensors to find relationships"
    },
    "compute_air_quality_index": {
        "patterns": [
            r"air.*quality.*index",
            r"aqi",
            r"calculate.*aqi",
            r"air.*quality.*score",
            r"iaq.*index"
        ],
        "description": "Computes composite Air Quality Index (AQI) from PM, CO2, VOC measurements"
    },
    "generate_health_alerts": {
        "patterns": [
            r"health.*alert",
            r"threshold.*violation",
            r"out.*of.*range",
            r"alarm.*generation",
            r"alert.*notification"
        ],
        "description": "Generates health alerts when sensor readings exceed configurable thresholds"
    },
    "detect_anomalies": {
        "patterns": [
            r"detect.*anomaly",
            r"anomaly.*detection",
            r"outlier.*detection",
            r"abnormal.*reading",
            r"unusual.*value"
        ],
        "description": "Detects statistical anomalies using z-score, modified z-score, or IQR methods"
    },
    "analyze_noise_levels": {
        "patterns": [
            r"noise.*level",
            r"sound.*level",
            r"acoustic.*analysis",
            r"decibel.*measurement",
            r"noise.*pollution"
        ],
        "description": "Analyzes noise levels with comfort and high-threshold classifications"
    },
    "analyze_air_quality": {
        "patterns": [
            r"analyze.*air.*quality",
            r"iaq.*analysis",
            r"indoor.*air",
            r"air.*quality.*assessment",
            r"ventilation.*quality"
        ],
        "description": "Comprehensive indoor air quality analysis including CO2, PM, VOC, and comfort indices"
    },
    "analyze_formaldehyde_levels": {
        "patterns": [
            r"formaldehyde",
            r"hcho",
            r"formaldehyde.*level",
            r"formaldehyde.*concentration",
            r"volatile.*organic"
        ],
        "description": "Analyzes formaldehyde (HCHO) levels with health-based threshold classifications"
    },
    "analyze_pm_levels": {
        "patterns": [
            r"particulate.*matter",
            r"pm2\\.5",
            r"pm10",
            r"particle.*level",
            r"dust.*level"
        ],
        "description": "Analyzes particulate matter (PM2.5, PM10) levels with AQI classifications"
    },
    "analyze_temperatures": {
        "patterns": [
            r"temperature.*analysis",
            r"thermal.*analysis",
            r"temp.*reading",
            r"temperature.*distribution",
            r"temperature.*statistics"
        ],
        "description": "Comprehensive temperature analysis with statistics, trends, and comfort assessment"
    },
    "analyze_humidity": {
        "patterns": [
            r"humidity.*analysis",
            r"rh.*analysis",
            r"moisture.*level",
            r"relative.*humidity",
            r"humidity.*distribution"
        ],
        "description": "Analyzes relative humidity levels with comfort range and condensation risk assessment"
    },
    "analyze_temperature_humidity": {
        "patterns": [
            r"temperature.*humidity",
            r"temp.*rh",
            r"thermal.*comfort",
            r"heat.*index",
            r"comfort.*analysis"
        ],
        "description": "Combined temperature and humidity analysis for thermal comfort assessment"
    },
    "detect_potential_failures": {
        "patterns": [
            r"potential.*failure",
            r"predict.*fault",
            r"failure.*prediction",
            r"equipment.*risk",
            r"proactive.*maintenance"
        ],
        "description": "Detects potential equipment failures based on anomaly patterns in recent time window"
    },
    "forecast_downtimes": {
        "patterns": [
            r"forecast.*downtime",
            r"predict.*outage",
            r"downtime.*prediction",
            r"maintenance.*forecast",
            r"availability.*forecast"
        ],
        "description": "Forecasts potential system downtimes using trend extrapolation methods"
    },
    "analyze_tvoc_levels": {
        "patterns": [
            r"tvoc",
            r"total.*volatile.*organic",
            r"voc.*level",
            r"organic.*compound",
            r"chemical.*pollutant"
        ],
        "description": "Analyzes Total Volatile Organic Compounds (TVOC) with health-based thresholds"
    },
    "analyze_ammonia_levels": {
        "patterns": [
            r"ammonia",
            r"nh3",
            r"ammonia.*level",
            r"ammonia.*concentration",
            r"nitrogen.*compound"
        ],
        "description": "Analyzes ammonia (NH3) concentration levels with exposure limit classifications"
    },
    "analyze_missing_data_scan": {
        "patterns": [
            r"missing.*data",
            r"data.*gap",
            r"incomplete.*data",
            r"data.*quality.*check",
            r"data.*completeness"
        ],
        "description": "Scans for missing data points and gaps in expected sensor reading frequency"
    },
    "analyze_flatline_detector": {
        "patterns": [
            r"flatline",
            r"stuck.*sensor",
            r"constant.*value",
            r"sensor.*frozen",
            r"no.*variation"
        ],
        "description": "Detects flatlined sensors (unchanging values) indicating sensor malfunction"
    },
    "analyze_spike_outliers": {
        "patterns": [
            r"spike",
            r"sudden.*change",
            r"outlier",
            r"jump.*in.*value",
            r"abnormal.*spike"
        ],
        "description": "Detects sudden spikes and outliers using IQR or z-score methods"
    },
    "analyze_sensor_drift_bias": {
        "patterns": [
            r"sensor.*drift",
            r"bias.*detection",
            r"calibration.*drift",
            r"measurement.*bias",
            r"systematic.*error"
        ],
        "description": "Analyzes sensor drift and bias by comparing against reference sensors"
    },
    "analyze_range_validation": {
        "patterns": [
            r"range.*validation",
            r"value.*in.*range",
            r"reading.*bounds",
            r"limit.*check",
            r"out.*of.*range"
        ],
        "description": "Validates sensor readings against acceptable physical or operational ranges"
    },
    "analyze_timestamp_consistency": {
        "patterns": [
            r"timestamp.*consistency",
            r"time.*gap",
            r"temporal.*consistency",
            r"data.*frequency",
            r"timing.*issue"
        ],
        "description": "Analyzes timestamp consistency and identifies irregular sampling intervals"
    },
    "analyze_iaq_composite": {
        "patterns": [
            r"iaq.*composite",
            r"overall.*air.*quality",
            r"composite.*iaq",
            r"air.*quality.*score",
            r"integrated.*iaq"
        ],
        "description": "Computes composite Indoor Air Quality score from multiple parameters (CO2, PM, TVOC, temp, RH)"
    },
    "analyze_humidity_profile": {
        "patterns": [
            r"humidity.*profile",
            r"rh.*profile",
            r"moisture.*pattern",
            r"humidity.*distribution",
            r"humidity.*comfort"
        ],
        "description": "Analyzes humidity profile with comfort range compliance and condensation risk"
    },
    "analyze_dewpoint_tracking": {
        "patterns": [
            r"dew.*point",
            r"dewpoint",
            r"condensation.*point",
            r"moisture.*condensation",
            r"dew.*temperature"
        ],
        "description": "Calculates and tracks dew point temperature for condensation risk analysis"
    },
    "analyze_air_enthalpy_grains": {
        "patterns": [
            r"enthalpy",
            r"moisture.*content",
            r"humidity.*ratio",
            r"grains.*moisture",
            r"psychrometric"
        ],
        "description": "Calculates air enthalpy and moisture content (grains) for psychrometric analysis"
    },
    "analyze_zone_iaq_compliance": {
        "patterns": [
            r"zone.*iaq",
            r"zone.*compliance",
            r"zone.*air.*quality",
            r"space.*iaq",
            r"room.*air.*quality"
        ],
        "description": "Assesses zone-level IAQ compliance against CO2 and RH standards"
    },
    "analyze_iaq_contrast_outdoor_indoor": {
        "patterns": [
            r"outdoor.*indoor.*comparison",
            r"outside.*inside.*air",
            r"outdoor.*vs.*indoor",
            r"fresh.*air.*vs.*indoor",
            r"ventilation.*effectiveness"
        ],
        "description": "Contrasts outdoor and indoor air quality to assess ventilation effectiveness"
    },
    "analyze_zone_temperature_summary": {
        "patterns": [
            r"zone.*temperature",
            r"space.*temperature",
            r"room.*temperature",
            r"zone.*thermal",
            r"multi.*zone.*temp"
        ],
        "description": "Summarizes temperature statistics and comfort compliance across zones"
    },
    "analyze_simple_comfort_index": {
        "patterns": [
            r"comfort.*index",
            r"thermal.*comfort",
            r"comfort.*score",
            r"occupant.*comfort",
            r"pmv"
        ],
        "description": "Calculates simple comfort index based on temperature and humidity targets"
    },
    "analyze_pmv_ppd_approximation": {
        "patterns": [
            r"pmv",
            r"ppd",
            r"predicted.*mean.*vote",
            r"percentage.*dissatisfied",
            r"fanger"
        ],
        "description": "Approximates PMV (Predicted Mean Vote) and PPD (Percentage People Dissatisfied) for thermal comfort"
    },
    "analyze_temperature_setpoint_tracking": {
        "patterns": [
            r"setpoint.*tracking",
            r"temperature.*control",
            r"setpoint.*deviation",
            r"control.*performance",
            r"target.*tracking"
        ],
        "description": "Tracks how well actual temperatures follow their setpoints for control performance"
    },
    "analyze_setpoint_deviation": {
        "patterns": [
            r"setpoint.*deviation",
            r"control.*error",
            r"offset.*from.*setpoint",
            r"setpoint.*difference",
            r"target.*deviation"
        ],
        "description": "Analyzes deviation between actual values and setpoints with tolerance bands"
    },
    "analyze_mixed_air_validation": {
        "patterns": [
            r"mixed.*air",
            r"mat.*validation",
            r"outdoor.*return.*mix",
            r"economizer.*mixing",
            r"air.*mixing"
        ],
        "description": "Validates mixed air temperature calculations in HVAC economizer systems"
    },
    "analyze_economizer_opportunity": {
        "patterns": [
            r"economizer.*opportunity",
            r"free.*cooling",
            r"outdoor.*air.*cooling",
            r"economizer.*mode",
            r"airside.*economizer"
        ],
        "description": "Identifies opportunities for economizer operation (free cooling) based on outdoor conditions"
    },
    "analyze_supply_air_temp_control": {
        "patterns": [
            r"supply.*air.*temp",
            r"sat.*control",
            r"discharge.*temp",
            r"supply.*temp.*control",
            r"sat.*performance"
        ],
        "description": "Analyzes supply air temperature control performance and setpoint tracking"
    },
    "analyze_supply_static_pressure_control": {
        "patterns": [
            r"static.*pressure.*control",
            r"duct.*pressure",
            r"supply.*pressure",
            r"pressure.*control.*performance",
            r"ssp.*control"
        ],
        "description": "Analyzes static pressure control performance in supply duct systems"
    },
    "analyze_airflow_profiling": {
        "patterns": [
            r"airflow.*profile",
            r"cfm.*profile",
            r"air.*volume",
            r"ventilation.*rate",
            r"airflow.*distribution"
        ],
        "description": "Profiles airflow rates and volumes across ventilation system"
    },
    "analyze_filter_health": {
        "patterns": [
            r"filter.*health",
            r"filter.*condition",
            r"filter.*pressure.*drop",
            r"filter.*replacement",
            r"filter.*status"
        ],
        "description": "Assesses air filter health based on differential pressure measurements"
    },
    "analyze_damper_performance": {
        "patterns": [
            r"damper.*performance",
            r"damper.*control",
            r"damper.*position",
            r"damper.*stuck",
            r"modulating.*damper"
        ],
        "description": "Analyzes damper performance, detecting stuck or malfunctioning dampers"
    },
    "analyze_coil_delta_t_effectiveness": {
        "patterns": [
            r"coil.*delta.*t",
            r"coil.*effectiveness",
            r"coil.*performance",
            r"heating.*cooling.*coil",
            r"heat.*transfer.*effectiveness"
        ],
        "description": "Analyzes heating/cooling coil effectiveness via temperature delta measurements"
    },
    "analyze_frost_freeze_risk": {
        "patterns": [
            r"frost.*risk",
            r"freeze.*protection",
            r"freezing.*condition",
            r"low.*temp.*alarm",
            r"freeze.*prevention"
        ],
        "description": "Assesses frost and freeze risk for HVAC coils based on outdoor air temperature"
    },
    "analyze_return_mixed_outdoor_consistency": {
        "patterns": [
            r"return.*mixed.*outdoor",
            r"rat.*mat.*oat",
            r"air.*temperature.*consistency",
            r"air.*side.*validation",
            r"airstream.*validation"
        ],
        "description": "Validates consistency between return, mixed, and outdoor air temperatures"
    },
    "analyze_chilled_water_delta_t": {
        "patterns": [
            r"chilled.*water.*delta.*t",
            r"chw.*delta.*t",
            r"chiller.*temperature.*difference",
            r"chilled.*water.*return",
            r"chiller.*supply.*return"
        ],
        "description": "Analyzes chilled water supply-return temperature delta for chiller performance"
    },
    "analyze_chilled_water_flow_health": {
        "patterns": [
            r"chilled.*water.*flow",
            r"chw.*flow",
            r"chiller.*flow.*rate",
            r"water.*flow.*health",
            r"chiller.*circulation"
        ],
        "description": "Assesses chilled water flow health and detects flow-related issues"
    },
    "analyze_loop_differential_pressure": {
        "patterns": [
            r"loop.*differential.*pressure",
            r"loop.*dp",
            r"chiller.*loop.*pressure",
            r"hydronic.*pressure",
            r"water.*loop.*pressure"
        ],
        "description": "Analyzes differential pressure in hydronic loops (chilled/hot water)"
    },
    "analyze_coil_valve_diagnostics": {
        "patterns": [
            r"coil.*valve",
            r"valve.*diagnostic",
            r"valve.*stuck",
            r"control.*valve",
            r"valve.*performance"
        ],
        "description": "Diagnoses coil valve operation, detecting stuck or hunting valves"
    },
    "analyze_heat_exchanger_effectiveness": {
        "patterns": [
            r"heat.*exchanger",
            r"heat.*recovery",
            r"hx.*effectiveness",
            r"energy.*recovery",
            r"heat.*wheel"
        ],
        "description": "Calculates heat exchanger effectiveness for energy recovery systems"
    },
    "analyze_condenser_loop_health": {
        "patterns": [
            r"condenser.*loop",
            r"condenser.*water",
            r"cooling.*tower",
            r"condenser.*health",
            r"cwl.*health"
        ],
        "description": "Assesses condenser water loop health and cooling tower performance"
    },
    "analyze_electric_power_summary": {
        "patterns": [
            r"electric.*power",
            r"power.*consumption",
            r"electricity.*usage",
            r"kw.*demand",
            r"power.*summary"
        ],
        "description": "Summarizes electrical power consumption, demand, and energy usage"
    },
    "analyze_load_profile": {
        "patterns": [
            r"load.*profile",
            r"demand.*profile",
            r"power.*profile",
            r"usage.*pattern",
            r"consumption.*pattern"
        ],
        "description": "Analyzes electrical load profile with peak, base, and time-of-use patterns"
    },
    "analyze_demand_response_readiness": {
        "patterns": [
            r"demand.*response",
            r"load.*shed",
            r"peak.*shaving",
            r"dr.*readiness",
            r"grid.*response"
        ],
        "description": "Assesses demand response readiness and load shedding potential"
    },
    "analyze_part_load_ratio": {
        "patterns": [
            r"part.*load.*ratio",
            r"plr",
            r"equipment.*loading",
            r"capacity.*utilization",
            r"load.*factor"
        ],
        "description": "Calculates part load ratio for equipment capacity utilization analysis"
    },
    "analyze_cooling_cop": {
        "patterns": [
            r"cooling.*cop",
            r"chiller.*efficiency",
            r"coefficient.*performance",
            r"cooling.*efficiency",
            r"chiller.*cop"
        ],
        "description": "Calculates Coefficient of Performance (COP) for cooling equipment"
    },
    "analyze_eer_seer": {
        "patterns": [
            r"eer",
            r"seer",
            r"energy.*efficiency.*ratio",
            r"seasonal.*efficiency",
            r"ac.*efficiency"
        ],
        "description": "Calculates EER (Energy Efficiency Ratio) and SEER estimates for AC systems"
    },
    "analyze_eui": {
        "patterns": [
            r"eui",
            r"energy.*use.*intensity",
            r"energy.*per.*area",
            r"building.*energy.*performance",
            r"kwh.*per.*m2"
        ],
        "description": "Calculates Energy Use Intensity (EUI) normalized by building area"
    },
    "analyze_fan_vfd_efficiency": {
        "patterns": [
            r"fan.*vfd",
            r"fan.*efficiency",
            r"variable.*frequency.*drive",
            r"fan.*motor.*efficiency",
            r"fan.*power"
        ],
        "description": "Analyzes fan VFD operation and energy efficiency at different speeds"
    },
    "analyze_pump_efficiency": {
        "patterns": [
            r"pump.*efficiency",
            r"pump.*performance",
            r"pump.*power",
            r"pump.*motor",
            r"hydronic.*pump"
        ],
        "description": "Analyzes pump efficiency and performance characteristics"
    },
    "analyze_runtime_analysis": {
        "patterns": [
            r"runtime",
            r"operating.*hours",
            r"run.*time",
            r"equipment.*hours",
            r"operational.*duration"
        ],
        "description": "Analyzes equipment runtime hours and operational patterns"
    },
    "analyze_schedule_compliance": {
        "patterns": [
            r"schedule.*compliance",
            r"operating.*schedule",
            r"occupancy.*schedule",
            r"after.*hours.*operation",
            r"schedule.*adherence"
        ],
        "description": "Checks equipment operation compliance against defined schedules"
    },
    "analyze_equipment_cycling_health": {
        "patterns": [
            r"equipment.*cycling",
            r"short.*cycling",
            r"start.*stop.*frequency",
            r"cycling.*behavior",
            r"hunting"
        ],
        "description": "Analyzes equipment cycling behavior to detect short cycling issues"
    },
    "analyze_alarm_event_summary": {
        "patterns": [
            r"alarm.*summary",
            r"event.*log",
            r"fault.*history",
            r"alert.*summary",
            r"alarm.*count"
        ],
        "description": "Summarizes alarm events and fault occurrences over time"
    },
    "analyze_sensor_correlation_map": {
        "patterns": [
            r"sensor.*correlation",
            r"correlation.*matrix",
            r"sensor.*relationship",
            r"cross.*correlation",
            r"data.*correlation"
        ],
        "description": "Creates correlation map showing relationships between multiple sensors"
    },
    "analyze_lead_lag": {
        "patterns": [
            r"lead.*lag",
            r"time.*delay",
            r"lag.*analysis",
            r"response.*delay",
            r"cross.*correlation.*lag"
        ],
        "description": "Analyzes lead-lag relationships and time delays between sensor pairs"
    },
    "analyze_weather_normalization": {
        "patterns": [
            r"weather.*normalization",
            r"temperature.*adjustment",
            r"degree.*day",
            r"climate.*normalization",
            r"hdd.*cdd"
        ],
        "description": "Normalizes energy consumption by weather (heating/cooling degree days)"
    },
    "analyze_change_point_detection": {
        "patterns": [
            r"change.*point",
            r"regime.*change",
            r"step.*change",
            r"behavior.*change",
            r"pattern.*shift"
        ],
        "description": "Detects change points where sensor behavior or patterns shift significantly"
    },
    "analyze_short_horizon_forecasting": {
        "patterns": [
            r"forecast",
            r"prediction",
            r"future.*value",
            r"next.*hour",
            r"short.*term.*forecast"
        ],
        "description": "Provides short-horizon (next N steps) forecasting using exponential smoothing"
    },
    "analyze_anomaly_detection_statistical": {
        "patterns": [
            r"statistical.*anomaly",
            r"z.*score.*anomaly",
            r"outlier.*detection",
            r"abnormal.*detection",
            r"statistical.*outlier"
        ],
        "description": "Statistical anomaly detection using z-score methodology"
    },
    "analyze_ach": {
        "patterns": [
            r"air.*change.*per.*hour",
            r"ach",
            r"ventilation.*rate",
            r"air.*exchange.*rate",
            r"room.*air.*change"
        ],
        "description": "Calculates Air Changes per Hour (ACH) for ventilation assessment"
    },
    "analyze_ventilation_effectiveness": {
        "patterns": [
            r"ventilation.*effectiveness",
            r"outdoor.*air.*delivery",
            r"fresh.*air.*supply",
            r"co2.*removal",
            r"ventilation.*adequacy"
        ],
        "description": "Assesses ventilation effectiveness based on CO2 removal and fresh air delivery"
    },
    "analyze_outdoor_air_fraction": {
        "patterns": [
            r"outdoor.*air.*fraction",
            r"oa.*fraction",
            r"fresh.*air.*percentage",
            r"minimum.*outdoor.*air",
            r"ventilation.*ratio"
        ],
        "description": "Calculates outdoor air fraction in supply air for ventilation compliance"
    },
    "analyze_setpoint_compliance": {
        "patterns": [
            r"setpoint.*compliance",
            r"setpoint.*tracking",
            r"control.*accuracy",
            r"within.*tolerance",
            r"setpoint.*deviation"
        ],
        "description": "Checks setpoint compliance with configurable tolerance bands"
    },
    "analyze_hunting_oscillation": {
        "patterns": [
            r"hunting",
            r"oscillation",
            r"control.*instability",
            r"cycling.*control",
            r"unstable.*control"
        ],
        "description": "Detects hunting and oscillation in control loops indicating tuning issues"
    },
    "analyze_actuator_stiction": {
        "patterns": [
            r"stiction",
            r"stuck.*actuator",
            r"valve.*sticking",
            r"damper.*stiction",
            r"actuator.*binding"
        ],
        "description": "Detects actuator stiction (stuck positions) in valves and dampers"
    },
    "analyze_illuminance_luminance_tracking": {
        "patterns": [
            r"illuminance",
            r"lighting.*level",
            r"lux",
            r"light.*intensity",
            r"luminance"
        ],
        "description": "Tracks illuminance/luminance levels for lighting quality assessment"
    },
    "analyze_noise_monitoring": {
        "patterns": [
            r"noise.*monitoring",
            r"sound.*level.*monitoring",
            r"acoustic.*monitoring",
            r"noise.*comfort",
            r"noise.*threshold"
        ],
        "description": "Monitors noise levels with comfort and high-threshold classifications"
    },
    "analyze_sensor_swap_bias_inference": {
        "patterns": [
            r"sensor.*swap",
            r"mismatched.*sensor",
            r"sensor.*mix.*up",
            r"sensor.*labeling",
            r"sensor.*identification"
        ],
        "description": "Infers potential sensor swaps or bias by comparing expected vs actual patterns"
    },
    "analyze_economizer_fault_rules": {
        "patterns": [
            r"economizer.*fault",
            r"economizer.*diagnostic",
            r"economizer.*fdd",
            r"free.*cooling.*fault",
            r"outdoor.*air.*damper.*fault"
        ],
        "description": "Applies fault detection rules for economizer operation and damper control"
    },
    "analyze_low_delta_t_syndrome": {
        "patterns": [
            r"low.*delta.*t",
            r"delta.*t.*syndrome",
            r"poor.*temperature.*difference",
            r"chiller.*delta.*t.*problem",
            r"low.*dt"
        ],
        "description": "Detects low delta-T syndrome in chilled water systems reducing efficiency"
    },
    "analyze_simultaneous_heating_cooling": {
        "patterns": [
            r"simultaneous.*heating.*cooling",
            r"fighting.*mode",
            r"heating.*and.*cooling",
            r"energy.*waste",
            r"control.*conflict"
        ],
        "description": "Detects simultaneous heating and cooling waste (fighting mode)"
    },
    "analyze_benchmarking_dashboard": {
        "patterns": [
            r"benchmarking",
            r"performance.*metric",
            r"kpi.*dashboard",
            r"benchmark.*comparison",
            r"performance.*summary"
        ],
        "description": "Creates benchmarking dashboard with key performance metrics and comparisons"
    },
    "analyze_control_loop_auto_tuning_aid": {
        "patterns": [
            r"control.*tuning",
            r"pid.*tuning",
            r"auto.*tuning",
            r"controller.*optimization",
            r"tuning.*parameters"
        ],
        "description": "Provides control loop tuning guidance based on performance characteristics"
    },
    "analyze_residual_based_coil_fdd": {
        "patterns": [
            r"coil.*fault.*detection",
            r"residual.*analysis",
            r"coil.*fdd",
            r"fouling.*detection",
            r"coil.*degradation"
        ],
        "description": "Residual-based fault detection and diagnostics for heating/cooling coils"
    },
    "analyze_per_person_ventilation_rate": {
        "patterns": [
            r"per.*person.*ventilation",
            r"cfm.*per.*person",
            r"ventilation.*per.*occupant",
            r"outdoor.*air.*per.*person",
            r"l/s.*per.*person"
        ],
        "description": "Calculates ventilation rate per person for occupancy-based compliance"
    },
    "analyze_baseline_energy_regression": {
        "patterns": [
            r"baseline.*energy",
            r"energy.*regression",
            r"energy.*model",
            r"baseline.*model",
            r"regression.*analysis"
        ],
        "description": "Creates baseline energy regression model for M&V and savings verification"
    },
    "analyze_load_zone_clustering": {
        "patterns": [
            r"load.*clustering",
            r"zone.*grouping",
            r"pattern.*clustering",
            r"usage.*classification",
            r"behavior.*clustering"
        ],
        "description": "Clusters zones or loads by similar patterns using k-means clustering"
    },
    "analyze_predictive_maintenance_fans_pumps": {
        "patterns": [
            r"predictive.*maintenance.*fan",
            r"predictive.*maintenance.*pump",
            r"fan.*predictive",
            r"pump.*predictive",
            r"fan.*pump.*health"
        ],
        "description": "Predictive maintenance assessment for fans and pumps based on vibration/power"
    },
    "analyze_predictive_maintenance_chillers_ahus": {
        "patterns": [
            r"predictive.*maintenance.*chiller",
            r"predictive.*maintenance.*ahu",
            r"chiller.*predictive",
            r"ahu.*predictive",
            r"chiller.*ahu.*health"
        ],
        "description": "Predictive maintenance assessment for chillers and AHUs"
    },
    "analyze_dr_event_impact_analysis": {
        "patterns": [
            r"dr.*event.*impact",
            r"demand.*response.*event",
            r"load.*shed.*impact",
            r"dr.*performance",
            r"event.*analysis"
        ],
        "description": "Analyzes impact and performance of demand response events"
    },
    "analyze_digital_twin_simulation": {
        "patterns": [
            r"digital.*twin",
            r"building.*simulation",
            r"model.*simulation",
            r"what.*if.*scenario",
            r"predictive.*model"
        ],
        "description": "Digital twin simulation for what-if scenarios and predictive analysis"
    },
    "analyze_mpc_readiness_shadow_mode": {
        "patterns": [
            r"mpc.*readiness",
            r"model.*predictive.*control",
            r"shadow.*mode",
            r"advanced.*control",
            r"optimal.*control"
        ],
        "description": "Assesses Model Predictive Control (MPC) readiness in shadow mode"
    },
    "analyze_fault_signature_library_matching": {
        "patterns": [
            r"fault.*signature",
            r"pattern.*matching",
            r"fault.*library",
            r"signature.*matching",
            r"known.*fault"
        ],
        "description": "Matches observed patterns against fault signature library for diagnosis"
    },
    "analyze_sat_residual_analysis": {
        "patterns": [
            r"sat.*residual",
            r"supply.*air.*temp.*residual",
            r"sat.*fault",
            r"sat.*diagnostic",
            r"discharge.*temp.*residual"
        ],
        "description": "Residual analysis for supply air temperature control fault detection"
    },
    "analyze_weather_normalized_benchmarking": {
        "patterns": [
            r"weather.*normalized.*benchmark",
            r"climate.*adjusted.*comparison",
            r"normalized.*performance",
            r"weather.*adjusted.*eui",
            r"degree.*day.*normalized"
        ],
        "description": "Weather-normalized benchmarking for fair building performance comparison"
    },
}

print(f"Total decorators defined: {len(FUNCTION_DECORATORS)}")
print("\nSample decorator:")
print(f"analyze_recalibration_frequency:")
print(f"  Patterns: {len(FUNCTION_DECORATORS['analyze_recalibration_frequency']['patterns'])}")
print(f"  Description: {FUNCTION_DECORATORS['analyze_recalibration_frequency']['description']}")
