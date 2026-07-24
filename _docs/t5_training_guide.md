---
layout: post
title: T5 Model Training Guide
date: 2025-10-08
---

# T5 Model Training Guide

Complete guide for training and deploying the T5 NL2SPARQL model using the web-based GUI.

## Overview

The T5 Model Training feature allows you to:
- **Add training examples** through an intuitive web interface
- **Train incrementally** without restarting from scratch
- **Monitor progress** with real-time logs and metrics
- **Deploy models** to production with one click
- **Test translations** instantly with the built-in playground

**Access**: Settings → T5 Model Training tab (`http://localhost:3000/settings`)

## What is NL2SPARQL?

NL2SPARQL is a T5-based transformer model that translates natural language questions into SPARQL queries for querying the building's knowledge graph.

**Example:**
```
Input:  "What is the temperature in zone 5.04?"
Output: SELECT ?value WHERE { 
          <sensor:Air_Temperature_Sensor_5.04> brick:hasValue ?value 
        }
```

## Getting Started

### Prerequisites

1. **Microservices running** on port 6001
2. **Sensor list available** (auto-detected from building)
3. **Transformers directory** mounted in Docker

### Architecture

```
Frontend (React)
    ↓
Microservices API (Flask)  [port 6001]
    ↓
T5 Training Script (quick_train.py)
    ↓
Trained Model Checkpoints
    ↓
NL2SPARQL Service (deployment)
```

## Training Workflow

### Step 1: Add Training Examples

#### Form Fields

**1. Question*** (Required)
- Natural language question about the building
- Should be realistic and commonly asked
- Can include sensor names, locations, or time references

**Examples:**
```
What is the CO2 level in zone 5.04?
Show me temperature readings for room 2.11 today
What is the average humidity in the building?
Are there any temperature anomalies in zone 5.05?
```

**2. Sensors Involved** (Optional)
- Multi-select dropdown with all building sensors
- Auto-populated from `sensor_list.txt`
- Sensor count by building:
  - Building 1 (ABACWS): **680 sensors**
  - Building 2 (Office): **329 sensors**
  - Building 3 (Data Center): **597 sensors**

**How to select:**
- Type to search (e.g., "temperature")
- Click to add multiple sensors
- Click `×` on tag to remove

**Why specify sensors?**
- Helps model learn sensor-question associations
- Improves translation accuracy
- Enables multi-sensor queries

**3. SPARQL Query*** (Required)
- The target SPARQL query the model should generate
- Must be valid SPARQL syntax
- Can use Brick Schema predicates

**Example:**
```sparql
PREFIX brick: <https://brickschema.org/schema/Brick#>
SELECT ?value WHERE {
  <http://example.org/sensor/Air_Temperature_Sensor_5.04> 
  brick:hasValue ?value .
}
```

**4. Category** (Optional)
- Classification for organizing examples
- Options: `user_defined`, `system_generated`, `imported`, etc.
- Helps filter and manage examples later

**5. Notes** (Optional)
- Additional context or explanations
- Edge cases or special handling notes
- Future improvements needed

#### Adding Examples

1. Fill in all required fields (marked with *)
2. Select relevant sensors (optional but recommended)
3. Validate SPARQL syntax
4. Click **"Add Example"**
5. Example appears in the "Training Examples" table

#### Editing Examples

1. Find example in the table
2. Click **"Edit"** button
3. Form populates with existing values
4. Make changes
5. Click **"Update Example"**

#### Deleting Examples

1. Find example in the table
2. Click **"Delete"** button
3. Confirm deletion
4. Example removed from training set

### Step 2: View Training Examples

The **Training Examples Table** shows all current examples:

**Columns:**
- **#**: Row number
- **Question**: The input text
- **SPARQL Query**: Target output (truncated)
- **Sensors**: Count of involved sensors
- **Category**: Classification tag
- **Actions**: Edit/Delete buttons

**Features:**
- **Pagination**: 10 examples per page
- **Search**: Filter by question text
- **Sort**: Click column headers
- **Export**: Download as JSON
- **Import**: Upload existing training data

**Example Count**: Shows total examples (e.g., "25 examples")

### Step 3: Configure Training

**Training Parameters:**

**Epochs** (Number of training cycles)
- Default: 10
- Range: 1-100
- More epochs = better accuracy but longer training
- Start with 5-10 for testing
- Use 20-50 for production

**Recommendations:**
- **Quick test**: 5 epochs (~2 minutes)
- **Standard**: 10 epochs (~5 minutes)
- **Production**: 30-50 epochs (~15-30 minutes)

### Step 4: Start Training

1. Set desired number of epochs (default: 10)
2. Click **"Start Training"** button
3. Training job starts immediately

**What happens:**
1. Examples saved to `correlation_fixes.json`
2. Training script (`quick_train.py`) executes
3. Model fine-tunes on new examples
4. Checkpoint saved incrementally
5. Progress reported every 10 steps

### Step 5: Monitor Training

**Real-Time Progress Bar**
- 0-100% completion
- Updates every 2 seconds
- Based on step count and total epochs

**Training Logs**
- Streaming output from training script
- Shows:
  - Loss values (lower is better)
  - Step numbers (e.g., "Step 50/500")
  - Completion percentage
  - Time elapsed
  - Final metrics

**Status Indicators:**
- 🔵 **idle**: Not training
- 🟡 **running**: Training in progress
- 🟢 **completed**: Successfully finished
- 🔴 **error**: Training failed

**Example Log Output:**
```
[10:30:15] Starting training with 25 examples, 10 epochs...
[10:30:18] Loaded base model: t5-base
[10:30:20] Step 10/500 - Loss: 2.341
[10:30:25] Step 50/500 - Loss: 1.854
[10:30:30] Step 100/500 - Loss: 1.456
...
[10:35:42] Step 500/500 - Loss: 0.234
[10:35:45] Training complete! Model saved to checkpoint-3
[10:35:45] Final validation loss: 0.198
```

### Step 6: View Available Models

**Models List** shows all trained checkpoints:

**Information Displayed:**
- **Model Name**: e.g., `checkpoint-3`
- **Created**: Timestamp of training completion
- **Examples**: Number of training examples used
- **Accuracy**: Validation metrics (if available)
- **Size**: Model file size in MB

**Actions per Model:**
- **Deploy**: Make this the production model
- **Delete**: Remove from storage (cannot undo)
- **Details**: View training configuration and metrics

### Step 7: Deploy Model

**Deployment Process:**

1. Click **"Deploy"** on desired model
2. Confirmation dialog appears
3. Confirm deployment
4. System performs:
   - Backs up current production model
   - Copies new model to production path
   - Restarts NL2SPARQL service (if running)
   - Updates model registry

**Deployment Time**: ~30 seconds

**Status Messages:**
- "Deploying model..."
- "Model deployed successfully!"
- "NL2SPARQL service restarted"

**Rollback**: If deployment fails, previous model is automatically restored

## API Endpoints

The T5 Training feature uses these REST API endpoints:

### 1. Get Sensors List
```http
GET /api/t5/sensors
```

**Response:**
```json
{
  "ok": true,
  "sensors": [
    "Air_Temperature_Sensor_5.01",
    "Air_Temperature_Sensor_5.02",
    "CO2_Level_Sensor_5.01",
    ...
  ]
}
```

### 2. Get Training Examples
```http
GET /api/t5/examples
```

**Response:**
```json
{
  "ok": true,
  "examples": [
    {
      "question": "What is the CO2 in zone 5.04?",
      "sparql": "SELECT ?value WHERE { ... }",
      "sensors": ["CO2_Level_Sensor_5.04"],
      "category": "user_defined",
      "notes": ""
    }
  ]
}
```

### 3. Add Training Example
```http
POST /api/t5/examples
Content-Type: application/json

{
  "question": "What is the temperature?",
  "sparql": "SELECT ?value WHERE { ... }",
  "sensors": ["Air_Temperature_Sensor_5.01"],
  "category": "user_defined",
  "notes": "Basic temperature query"
}
```

### 4. Start Training
```http
POST /api/t5/train
Content-Type: application/json

{
  "epochs": 10
}
```

**Response:**
```json
{
  "ok": true,
  "job_id": "train_20250108_103015",
  "message": "Training started"
}
```

### 5. Check Training Status
```http
GET /api/t5/train/{job_id}/status
```

**Response:**
```json
{
  "ok": true,
  "job": {
    "status": "running",
    "progress": 45,
    "logs": "Step 225/500 - Loss: 1.234..."
  }
}
```

### 6. Get Available Models
```http
GET /api/t5/models
```

**Response:**
```json
{
  "ok": true,
  "models": [
    {
      "name": "checkpoint-3",
      "path": "/app/Transformers/t5_base/trained/checkpoint-3",
      "created": "2025-01-08T10:35:45",
      "size_mb": 892.4
    }
  ]
}
```

### 7. Deploy Model
```http
POST /api/t5/deploy
Content-Type: application/json

{
  "model_name": "checkpoint-3"
}
```

## File Structure

### Training Data Location

```
Transformers/
└── t5_base/
    ├── training/
    │   ├── bldg1/
    │   │   └── correlation_fixes.json    ← Training examples
    │   ├── bldg2/
    │   │   └── correlation_fixes.json
    │   └── bldg3/
    │       └── correlation_fixes.json
    ├── trained/
    │   ├── checkpoint-1/                  ← Old checkpoints
    │   ├── checkpoint-2/
    │   └── checkpoint-3/                  ← Current model
    │       ├── config.json
    │       ├── pytorch_model.bin
    │       ├── tokenizer_config.json
    │       └── ...
    └── quick_train.py                     ← Training script
```

### Training Data Format

**File**: `correlation_fixes.json`

```json
{
  "pairs": [
    {
      "question": "What is the CO2 level in zone 5.04?",
      "sparql": "SELECT ?value WHERE { <sensor:CO2_Level_Sensor_5.04> brick:hasValue ?value }",
      "sensors": ["CO2_Level_Sensor_5.04"],
      "category": "user_defined",
      "notes": "Basic sensor value query",
      "timestamp": "2025-01-08T10:15:32Z"
    }
  ]
}
```

## Multi-Building Support

The T5 Training GUI automatically detects which building is active and loads the appropriate sensors:

### Auto-Detection Logic

```python
for building in ['bldg1', 'bldg2', 'bldg3']:
    sensor_file = f'/app/rasa-{building}/actions/sensor_list.txt'
    if os.path.exists(sensor_file):
        # Load sensors from this building
        break
```

### Building-Specific Data

 | Building | Sensors | Training File Location | 
 | ---------- | --------- | ------------------------ | 
 | Building 1 | 680 | `Transformers/t5_base/training/bldg1/` | 
 | Building 2 | 329 | `Transformers/t5_base/training/bldg2/` | 
 | Building 3 | 597 | `Transformers/t5_base/training/bldg3/` | 

### Switching Buildings

To switch training data between buildings:

1. Stop current building services:
```bash
docker-compose -f docker-compose.bldg1.yml down microservices
```

2. Start target building:
```bash
docker-compose -f docker-compose.bldg2.yml up -d microservices rasa-frontend
```

3. Refresh the Settings page
4. Sensor dropdown automatically updates

## Best Practices

### Training Examples

**DO:**
- ✅ Write natural, conversational questions
- ✅ Include variations of the same question
- ✅ Cover all sensor types in your building
- ✅ Test queries in Fuseki before adding
- ✅ Add context in notes field
- ✅ Use diverse SPARQL patterns

**DON'T:**
- ❌ Use technical jargon uncommon to users
- ❌ Write overly complex queries initially
- ❌ Add duplicate examples
- ❌ Skip sensor selection (when applicable)
- ❌ Use invalid SPARQL syntax

### Training Strategy

**Incremental Approach:**
1. Start with 10-20 basic examples
2. Train with 5 epochs (quick test)
3. Test translations
4. Add 10 more examples covering gaps
5. Train with 10 epochs
6. Repeat until satisfactory

**Production Deployment:**
1. Accumulate 100+ diverse examples
2. Train with 30-50 epochs
3. Validate on test set
4. Deploy to production
5. Monitor translation quality
6. Iterate based on user feedback

### Model Management

**Checkpoints:**
- Keep last 3-5 checkpoints
- Delete old checkpoints to save space
- Name checkpoints descriptively
- Document training configuration

**Backup Strategy:**
```bash
# Backup training data
cp Transformers/t5_base/training/bldg1/correlation_fixes.json \
   backups/correlation_fixes_$(date +%Y%m%d).json

# Backup production model
tar -czf backups/checkpoint-3_$(date +%Y%m%d).tar.gz \
   Transformers/t5_base/trained/checkpoint-3/
```

## Troubleshooting

### Sensor Dropdown Empty

**Problem**: "No options" shown in sensor dropdown

**Causes:**
1. Port 6000 blocked by Chrome (use port 6001)
2. Microservices not running
3. Volume mounts missing in docker-compose

**Solution:**
```bash
# 1. Check microservices is running
docker ps | grep microservices

# 2. Test API directly
curl http://localhost:6001/api/t5/sensors

# 3. Check docker-compose volume mounts
docker-compose -f docker-compose.bldg1.yml config | grep -A2 volumes
```

See: [Port 6000 Fix Documentation](../T5_TRAINING_PORT_FIX.md)

### Training Stuck

**Problem**: Training progress bar at 0% for >5 minutes

**Causes:**
1. Training script crashed
2. Insufficient memory
3. Invalid training data
4. GPU/CPU overload

**Solution:**
```bash
# Check container logs
docker logs microservices_container --tail 50

# Check system resources
docker stats microservices_container

# Restart microservices
docker-compose -f docker-compose.bldg1.yml restart microservices
```

### Training Fails

**Problem**: Status shows "error" with red indicator

**Check Logs For:**
- `JSON decode error`: Invalid training data format
- `CUDA out of memory`: Reduce batch size or use CPU
- `Permission denied`: Volume mount issues
- `Model not found`: Missing base T5 model

**Solutions:**
```bash
# Validate JSON
python -m json.tool < Transformers/t5_base/training/bldg1/correlation_fixes.json

# Check disk space
df -h

# Verify base model exists
ls -la Transformers/t5_base/trained/checkpoint-3/
```

### Model Won't Deploy

**Problem**: Deployment fails with error

**Common Issues:**
1. NL2SPARQL service not running
2. Checkpoint directory missing files
3. Permission errors

**Solution:**
```bash
# Check NL2SPARQL service
docker logs nl2sparql_service --tail 20

# Verify checkpoint integrity
ls -la Transformers/t5_base/trained/checkpoint-3/

# Restart NL2SPARQL
docker-compose -f docker-compose.extras.yml restart nl2sparql
```

## Advanced Topics

### Custom Training Script

Modify `Transformers/t5_base/quick_train.py` for:
- Custom learning rates
- Different batch sizes
- Advanced augmentation
- Multi-GPU training

### Hyperparameter Tuning

```python
# In quick_train.py
training_args = TrainingArguments(
    learning_rate=5e-5,        # Default: 5e-5
    per_device_train_batch_size=8,  # Adjust for memory
    num_train_epochs=epochs,
    warmup_steps=500,
    weight_decay=0.01,
    logging_steps=10,
    save_steps=500,
)
```

### Integration with NL2SPARQL

Once trained, your model is used by the NL2SPARQL service:

**Service Location**: `docker-compose.extras.yml`
**Port**: 6005
**Endpoint**: `POST /nl2sparql`

**Request:**
```json
{
  "question": "What is the temperature in zone 5.04?"
}
```

**Response:**
```json
{
  "sparql": "SELECT ?value WHERE { <sensor:Air_Temperature_Sensor_5.04> brick:hasValue ?value }",
  "confidence": 0.95
}
```

## Performance Metrics

### Training Time Estimates

 | Examples | Epochs | Hardware | Time | 
 | ---------- | -------- | ---------- | ------ | 
 | 10 | 5 | CPU | ~2 min | 
 | 25 | 10 | CPU | ~5 min | 
 | 50 | 20 | CPU | ~12 min | 
 | 100 | 30 | CPU | ~25 min | 
 | 100 | 30 | GPU (V100) | ~8 min | 

### Model Size

- **Base T5 Model**: ~892 MB
- **Fine-tuned Checkpoint**: ~892 MB (same size)
- **Training Data**: ~50 KB per 100 examples

### Translation Quality

Monitor these metrics:
- **Exact Match**: % queries matching ground truth exactly
- **Execution Success**: % queries that execute without errors
- **Semantic Match**: % queries returning correct results
- **User Satisfaction**: Feedback from actual users

## Next Steps

- [Frontend UI Guide](./frontend_ui.md)
- [Backend Services Documentation](./backend_services.md)
- [Multi-Building Guide](./multi_building.md)
- [API Reference](./api_reference.md)
