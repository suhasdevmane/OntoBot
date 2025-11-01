# Quick Start: Testing Typo-Tolerant Sensor Resolution

## 1. Rebuild Action Server (Required)
```powershell
# Navigate to project root
cd c:\Users\suhas\Documents\GitHub\OntoBot

# Rebuild bldg1 action server
docker-compose -f docker-compose.bldg1.yml build action_server_bldg1

# Start action server
docker-compose -f docker-compose.bldg1.yml up -d action_server_bldg1
```

## 2. Verify Deployment
```powershell
# Check logs for successful start
docker logs action_server_bldg1 --tail 50

# Look for:
# - "Rasa SDK server started"
# - No import errors
# - FUZZY_THRESHOLD logged (if set)
```

## 3. Test Queries

### Via Rasa UI (Recommended)
1. Open: http://localhost:3000
2. Test these queries:

**Basic typo test:**
```
what is NO2 sensor? what does it measure? where this NO2 Level sensor 5.09 is located?
```
Expected: No errors, sensor info returned

**Multiple spaces test:**
```
show me NO2  Level   Sensor  5.09
```
Expected: Correctly normalized to NO2_Level_Sensor_5.09

**Typo in word test:**
```
NO2 Levl Sensor 5.09
```
Expected: Fuzzy matched to NO2_Level_Sensor_5.09 (score ~97)

**Complex sensor test:**
```
Carbon Monoxide Coal Gas Liquefied MQ9 Gas Sensor 5.25
```
Expected: Extracted and canonicalized correctly

**Mixed format test:**
```
compare Air_Quality_Level_Sensor_5.01 with NO2 Level Sensor 5.09
```
Expected: Both sensors recognized

### Via REST API
```powershell
# Test with curl or Invoke-WebRequest
$body = @{
    sender = "test_user"
    message = "what is NO2 sensor? where this NO2 Level sensor 5.09 is located?"
} | ConvertTo-Json

Invoke-WebRequest -Uri "http://localhost:5005/webhooks/rest/webhook" `
    -Method POST `
    -ContentType "application/json" `
    -Body $body
```

## 4. Monitor Logs (Real-time)
```powershell
# Follow logs in real-time
docker logs action_server_bldg1 -f

# Look for these success indicators:
# "Extracted sensors from text: extracted_sensors=['NO2_Level_Sensor_5.09']"
# "Fuzzy-matched 'NO2_Level_Sensor_5.09' -> 'NO2_Level_Sensor_5.09' (score=100)"
# "Prepared NL2SPARQL payload: question_used='...NO2_Level_Sensor_5.09...'"
# "SPARQL postprocessing applied corrections"  # If any corrections made

# Look for these error indicators:
# "Fuzzy match error"  # Threshold too high or sensor not in list
# "Failed to extract sensors from text"  # Regex pattern issue
# "Parse error"  # SPARQL still malformed (shouldn't happen now)
```

## 5. Adjust Threshold (Optional)

If too many false positives (wrong sensors matched):
```yaml
# Edit docker-compose.bldg1.yml
action_server_bldg1:
  environment:
    - FUZZY_THRESHOLD=90  # Stricter
```

If too many false negatives (sensors not matched):
```yaml
action_server_bldg1:
  environment:
    - FUZZY_THRESHOLD=70  # More lenient
```

Then rebuild:
```powershell
docker-compose -f docker-compose.bldg1.yml build action_server_bldg1
docker-compose -f docker-compose.bldg1.yml up -d action_server_bldg1
```

## 6. Standalone Test (No Docker)
```powershell
cd c:\Users\suhas\Documents\GitHub\OntoBot\rasa-bldg1\actions
C:/Users/suhas/Documents/GitHub/OntoBot/.venv/Scripts/python.exe test_sensor_extraction.py
```

Expected output:
```
[Test 1]
Input: what is NO2 sensor? where this NO2 Level sensor 5.09 is located?
Extracted: 1 sensor(s)
  'NO2 Level sensor 5.09' -> 'NO2_Level_Sensor_5.09'
Rewritten: ...NO2_Level_Sensor_5.09...
```

## 7. Common Issues

### Issue: "Module not found: rapidfuzz"
**Docker**: Ensure `rapidfuzz` is in `requirements.txt`
**Local**: `pip install rapidfuzz`

### Issue: "No sensors extracted"
**Check**: Sensor exists in `sensor_list.txt`
**Action**: Lower `FUZZY_THRESHOLD` or fix sensor name

### Issue: "Wrong sensor matched"
**Check**: Similar sensor names in `sensor_list.txt`
**Action**: Increase `FUZZY_THRESHOLD` or review naming convention

### Issue: "SPARQL parse error" (still happening)
**Check**: Generated SPARQL in logs
**Action**: 
1. Check NL2SPARQL service health
2. Review SPARQL postprocessing patterns
3. Add specific fix pattern for your case

## 8. Rollback

If you need to revert:
```powershell
cd c:\Users\suhas\Documents\GitHub\OntoBot

# Revert changes
git checkout HEAD -- rasa-bldg1/actions/actions.py

# Rebuild
docker-compose -f docker-compose.bldg1.yml build action_server_bldg1
docker-compose -f docker-compose.bldg1.yml up -d action_server_bldg1
```

## 9. Next Building (bldg2/bldg3)

See full migration guide in: `TYPO_TOLERANT_SENSORS.md`

Quick steps:
1. Copy new methods to `rasa-bldg2/actions/actions.py`
2. Update `run()` integration
3. Ensure `sensor_list.txt` exists
4. Test with building-specific sensors
5. Deploy

## 10. Documentation

- **Full documentation**: `TYPO_TOLERANT_SENSORS.md`
- **Implementation details**: `IMPLEMENTATION_SUMMARY.md`
- **Test script**: `test_sensor_extraction.py`

## Success Indicators

✅ No SPARQL parse errors in logs  
✅ Sensor extraction logged for queries with sensors  
✅ Fuzzy match scores shown (if applicable)  
✅ Rewritten question logged (different from original)  
✅ Correct sensor data returned to user  

## Support

Check logs first: `docker logs action_server_bldg1 -f`

Review documentation in same folder as this file.
