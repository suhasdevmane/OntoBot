"""
Validation script for pure ML decider service.
Tests a diverse set of queries and validates responses.
"""
import requests
import json
from typing import List, Dict, Any


DECIDER_URL = "http://localhost:6009/decide"

# Test queries covering different analytics functions
TEST_QUERIES = [
    # Time-based analytics
    {
        "question": "show me time in range for CO2 in the last week",
        "expected_perform": True,
        "expected_analytics": ["percentage_time_in_range", "duration_in_range"]
    },
    {
        "question": "how long was temperature above setpoint yesterday",
        "expected_perform": True,
        "expected_analytics": ["duration_above_threshold", "percentage_time_above"]
    },
    
    # Ranking/aggregation
    {
        "question": "which sensors have the highest values right now",
        "expected_perform": True,
        "expected_analytics": ["top_n_by_latest", "max_value_per_sensor"]
    },
    {
        "question": "show me the top 5 rooms with lowest humidity",
        "expected_perform": True,
        "expected_analytics": ["top_n_by_latest", "bottom_n_by_average"]
    },
    
    # Statistical analytics
    {
        "question": "what's the average temperature trend over the past month",
        "expected_perform": True,
        "expected_analytics": ["average_over_time", "trend_analysis"]
    },
    {
        "question": "calculate standard deviation of CO2 readings",
        "expected_perform": True,
        "expected_analytics": ["standard_deviation", "variability_analysis"]
    },
    
    # Setpoint/threshold
    {
        "question": "how far are we from setpoint in zone temperature",
        "expected_perform": True,
        "expected_analytics": ["difference_from_setpoint", "deviation_from_target"]
    },
    {
        "question": "check if humidity exceeded 80% threshold",
        "expected_perform": True,
        "expected_analytics": ["threshold_crossings", "count_above_threshold"]
    },
    
    # Anomaly/failure detection
    {
        "question": "detect anomalies in power consumption data",
        "expected_perform": True,
        "expected_analytics": ["anomaly_detection", "outlier_detection"]
    },
    {
        "question": "analyze sensor failure patterns",
        "expected_perform": True,
        "expected_analytics": ["analyze_sensor_failures", "failure_frequency"]
    },
    
    # Correlation
    {
        "question": "find correlation between temperature and occupancy",
        "expected_perform": True,
        "expected_analytics": ["correlation_analysis", "cross_correlation"]
    },
    
    # Recalibration
    {
        "question": "suggest recalibration schedule for sensors",
        "expected_perform": True,
        "expected_analytics": ["analyze_recalibration_frequency", "recalibration_schedule"]
    },
    
    # Peak detection
    {
        "question": "identify peak usage times for lighting",
        "expected_perform": True,
        "expected_analytics": ["peak_detection", "identify_peaks"]
    },
    
    # Ontology queries (NO analytics)
    {
        "question": "list all temperature sensors in the building",
        "expected_perform": False,
        "expected_analytics": None
    },
    {
        "question": "show me the Brick schema for HVAC equipment",
        "expected_perform": False,
        "expected_analytics": None
    },
    {
        "question": "what rooms are in zone 2",
        "expected_perform": False,
        "expected_analytics": None
    },
    {
        "question": "describe the sensor hierarchy",
        "expected_perform": False,
        "expected_analytics": None
    },
]


def test_decider(query: str, expected_perform: bool, expected_analytics: List[str] = None, top_n: int = 3) -> Dict[str, Any]:
    """Test a single query against the decider service."""
    try:
        response = requests.post(
            DECIDER_URL,
            json={"question": query, "top_n": top_n},
            timeout=10
        )
        response.raise_for_status()
        result = response.json()
        
        # Validate response structure
        assert "perform_analytics" in result, "Missing perform_analytics"
        assert "confidence" in result, "Missing confidence"
        assert isinstance(result["confidence"], float), "Confidence not a float"
        assert 0.0 <= result["confidence"] <= 1.0, "Confidence out of range"
        
        # Check perform decision
        perform_match = result["perform_analytics"] == expected_perform
        
        # Check analytics prediction (if applicable)
        analytics_match = False
        if expected_perform and expected_analytics:
            predicted = result.get("analytics")
            analytics_match = predicted in expected_analytics if predicted else False
        elif not expected_perform:
            analytics_match = True  # Don't care about analytics if no perform
        
        # Extract top candidates
        candidates = result.get("candidates", [])
        top_candidates = [c["analytics"] for c in candidates[:3]]
        
        return {
            "query": query,
            "success": True,
            "perform_match": perform_match,
            "analytics_match": analytics_match,
            "expected_perform": expected_perform,
            "actual_perform": result["perform_analytics"],
            "expected_analytics": expected_analytics,
            "actual_analytics": result.get("analytics"),
            "confidence": result["confidence"],
            "top_candidates": top_candidates,
            "candidate_count": len(candidates)
        }
    
    except Exception as e:
        return {
            "query": query,
            "success": False,
            "error": str(e),
            "perform_match": False,
            "analytics_match": False
        }


def main():
    print("=" * 80)
    print("PURE ML DECIDER VALIDATION")
    print("=" * 80)
    print(f"Target: {DECIDER_URL}")
    print(f"Test queries: {len(TEST_QUERIES)}\n")
    
    # Check health
    try:
        health_resp = requests.get("http://localhost:6009/health", timeout=5)
        health_data = health_resp.json()
        print(f"Health check: {health_data}")
        
        if not health_data.get("perform_model_loaded") or not health_data.get("label_model_loaded"):
            print("\n✗ ERROR: Models not loaded! Train models first.")
            print("  Run: cd decider-service && python training/train.py")
            return
        
        print(f"  Mode: {health_data.get('mode', 'unknown')}")
        print(f"  Registry: {health_data.get('registry_count', 0)} functions\n")
    except Exception as e:
        print(f"\n✗ ERROR: Cannot reach decider service: {e}")
        print("  Ensure service is running: docker-compose up -d decider-service\n")
        return
    
    # Run tests
    results = []
    for test in TEST_QUERIES:
        result = test_decider(
            test["question"],
            test["expected_perform"],
            test.get("expected_analytics")
        )
        results.append(result)
    
    # Print results
    print("\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80)
    
    passed = 0
    failed = 0
    
    for result in results:
        if not result["success"]:
            print(f"\n✗ ERROR: {result['query']}")
            print(f"  {result.get('error')}")
            failed += 1
            continue
        
        status = "✓" if (result["perform_match"] and result["analytics_match"]) else "✗"
        
        print(f"\n{status} {result['query']}")
        print(f"  Expected perform: {result['expected_perform']} | Actual: {result['actual_perform']} | Confidence: {result['confidence']:.3f}")
        
        if result['expected_perform']:
            print(f"  Expected analytics: {result['expected_analytics']}")
            print(f"  Predicted: {result['actual_analytics']}")
            print(f"  Top-3 candidates: {', '.join(result['top_candidates'])}")
        
        if result["perform_match"] and result["analytics_match"]:
            passed += 1
        else:
            failed += 1
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total: {len(results)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Success rate: {passed / len(results) * 100:.1f}%")
    
    if failed == 0:
        print("\n✓ ALL TESTS PASSED! Pure ML decider is working correctly.")
    else:
        print(f"\n✗ {failed} tests failed. Review predictions and consider retraining.")
        print("  Tips:")
        print("  - Add more training examples for failed queries")
        print("  - Check registry metadata (patterns/descriptions)")
        print("  - Regenerate training data: python decider-service/data/generate_training_from_registry.py")


if __name__ == "__main__":
    main()
