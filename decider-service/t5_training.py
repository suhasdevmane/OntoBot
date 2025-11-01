"""
T5 Model Training API Blueprint

Provides REST API endpoints for:
- Managing training examples (CRUD operations)
- Training T5 model with quick training
- Monitoring training progress
- Deploying trained models

Author: AI Assistant
Date: October 2025
"""

from flask import Blueprint, request, jsonify, send_file
import json
import os
import subprocess
import threading
import uuid
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

t5_training_bp = Blueprint('t5_training', __name__)

# Path configurations
T5_BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../Transformers/t5_base'))
TRAINING_DATASET = os.path.join(T5_BASE_DIR, 'training/bldg1/correlation_fixes.json')

# For Docker: auto-detect which building's sensor list to use
# Check for mounted building directories in order (bldg1, bldg2, bldg3)
SENSOR_LIST_FILE = None
for building in ['bldg1', 'bldg2', 'bldg3']:
    docker_path = f'/app/rasa-{building}/actions/sensor_list.txt'
    local_path = os.path.join(os.path.dirname(__file__), f'../../rasa-{building}/actions/sensor_list.txt')
    
    if os.path.exists(docker_path):
        SENSOR_LIST_FILE = docker_path
        logger.info(f"Using sensor list from {building} (Docker path)")
        break
    elif os.path.exists(local_path):
        SENSOR_LIST_FILE = local_path
        logger.info(f"Using sensor list from {building} (local path)")
        break

if not SENSOR_LIST_FILE:
    logger.warning("No sensor_list.txt found for any building!")

# Training job tracking
training_jobs = {}

def load_sensor_list():
    """Load available sensors from sensor_list.txt"""
    try:
        if os.path.exists(SENSOR_LIST_FILE):
            with open(SENSOR_LIST_FILE, 'r') as f:
                sensors = [line.strip() for line in f if line.strip()]
            return sensors
        return []
    except Exception as e:
        logger.error(f"Error loading sensor list: {e}")
        return []

def load_training_examples():
    """Load training examples from JSON file"""
    try:
        if os.path.exists(TRAINING_DATASET):
            with open(TRAINING_DATASET, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    except Exception as e:
        logger.error(f"Error loading training examples: {e}")
        return []

def save_training_examples(examples):
    """Save training examples to JSON file"""
    try:
        os.makedirs(os.path.dirname(TRAINING_DATASET), exist_ok=True)
        with open(TRAINING_DATASET, 'w', encoding='utf-8') as f:
            json.dump(examples, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Error saving training examples: {e}")
        return False

@t5_training_bp.route('/api/t5/sensors', methods=['GET'])
def get_sensors():
    """Get list of available sensors"""
    try:
        sensors = load_sensor_list()
        return jsonify({'ok': True, 'sensors': sensors})
    except Exception as e:
        logger.error(f"Error in get_sensors: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500

@t5_training_bp.route('/api/t5/examples', methods=['GET'])
def get_examples():
    """Get all training examples"""
    try:
        examples = load_training_examples()
        return jsonify({'ok': True, 'examples': examples, 'count': len(examples)})
    except Exception as e:
        logger.error(f"Error in get_examples: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500

@t5_training_bp.route('/api/t5/examples', methods=['POST'])
def add_example():
    """Add a new training example"""
    try:
        data = request.json
        question = data.get('question', '').strip()
        entities = data.get('entities', [])
        sparql = data.get('sparql', '').strip()
        category = data.get('category', 'user_defined')
        notes = data.get('notes', '')
        
        if not question or not sparql:
            return jsonify({'ok': False, 'error': 'Question and SPARQL are required'}), 400
        
        examples = load_training_examples()
        
        new_example = {
            'question': question,
            'entities': entities,
            'sparql': sparql,
            'category': category,
            'notes': notes,
            'created_at': datetime.now().isoformat()
        }
        
        examples.append(new_example)
        
        if save_training_examples(examples):
            return jsonify({'ok': True, 'example': new_example, 'count': len(examples)})
        else:
            return jsonify({'ok': False, 'error': 'Failed to save example'}), 500
            
    except Exception as e:
        logger.error(f"Error in add_example: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500

@t5_training_bp.route('/api/t5/examples/<int:index>', methods=['DELETE'])
def delete_example(index):
    """Delete a training example by index"""
    try:
        examples = load_training_examples()
        
        if index < 0 or index >= len(examples):
            return jsonify({'ok': False, 'error': 'Invalid index'}), 400
        
        deleted = examples.pop(index)
        
        if save_training_examples(examples):
            return jsonify({'ok': True, 'deleted': deleted, 'count': len(examples)})
        else:
            return jsonify({'ok': False, 'error': 'Failed to save changes'}), 500
            
    except Exception as e:
        logger.error(f"Error in delete_example: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500

@t5_training_bp.route('/api/t5/examples/<int:index>', methods=['PUT'])
def update_example(index):
    """Update a training example by index"""
    try:
        data = request.json
        examples = load_training_examples()
        
        if index < 0 or index >= len(examples):
            return jsonify({'ok': False, 'error': 'Invalid index'}), 400
        
        question = data.get('question', '').strip()
        sparql = data.get('sparql', '').strip()
        
        if not question or not sparql:
            return jsonify({'ok': False, 'error': 'Question and SPARQL are required'}), 400
        
        examples[index] = {
            'question': question,
            'entities': data.get('entities', []),
            'sparql': sparql,
            'category': data.get('category', 'user_defined'),
            'notes': data.get('notes', ''),
            'updated_at': datetime.now().isoformat()
        }
        
        if save_training_examples(examples):
            return jsonify({'ok': True, 'example': examples[index], 'count': len(examples)})
        else:
            return jsonify({'ok': False, 'error': 'Failed to save changes'}), 500
            
    except Exception as e:
        logger.error(f"Error in update_example: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500

def run_training_job(job_id, epochs=10):
    """Background thread to run T5 training"""
    job = training_jobs[job_id]
    
    try:
        job['status'] = 'running'
        job['logs'] = 'Starting T5 model training...\n'
        job['progress'] = 0
        
        # Check if quick_train.py exists
        quick_train_script = os.path.join(T5_BASE_DIR, 'quick_train.py')
        if not os.path.exists(quick_train_script):
            job['status'] = 'error'
            job['error'] = f'Training script not found: {quick_train_script}'
            return
        
        # Run quick_train.py
        cmd = [
            'python',
            quick_train_script,
            '--dataset', TRAINING_DATASET,
            '--epochs', str(epochs),
            '--batch-size', '2',
            '--learning-rate', '3e-5'
        ]
        
        job['logs'] += f'Command: {" ".join(cmd)}\n\n'
        job['progress'] = 10
        
        process = subprocess.Popen(
            cmd,
            cwd=T5_BASE_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        # Stream output
        for line in iter(process.stdout.readline, ''):
            if line:
                job['logs'] += line
                
                # Update progress based on keywords
                if 'Epoch' in line:
                    job['progress'] = min(90, job['progress'] + 8)
                elif 'Saving Model' in line:
                    job['progress'] = 95
                elif 'Complete' in line:
                    job['progress'] = 100
        
        process.wait()
        
        if process.returncode == 0:
            job['status'] = 'completed'
            job['progress'] = 100
            job['logs'] += '\n\n✅ Training completed successfully!\n'
            job['model_path'] = os.path.join(T5_BASE_DIR, 'trained/quick-fix/checkpoint-quick-fix')
        else:
            job['status'] = 'error'
            job['error'] = f'Training failed with exit code {process.returncode}'
            job['logs'] += f'\n\n❌ Training failed with exit code {process.returncode}\n'
            
    except Exception as e:
        job['status'] = 'error'
        job['error'] = str(e)
        job['logs'] += f'\n\n❌ Error: {str(e)}\n'
        logger.error(f"Training job {job_id} failed: {e}")

@t5_training_bp.route('/api/t5/train', methods=['POST'])
def start_training():
    """Start a new T5 training job"""
    try:
        data = request.json or {}
        epochs = data.get('epochs', 10)
        
        # Validate training data exists
        examples = load_training_examples()
        if len(examples) == 0:
            return jsonify({'ok': False, 'error': 'No training examples found'}), 400
        
        # Create new job
        job_id = str(uuid.uuid4())
        training_jobs[job_id] = {
            'id': job_id,
            'status': 'starting',
            'progress': 0,
            'logs': '',
            'error': None,
            'started_at': datetime.now().isoformat(),
            'examples_count': len(examples),
            'epochs': epochs
        }
        
        # Start training in background thread
        thread = threading.Thread(target=run_training_job, args=(job_id, epochs))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'ok': True,
            'job_id': job_id,
            'message': f'Training started with {len(examples)} examples for {epochs} epochs'
        })
        
    except Exception as e:
        logger.error(f"Error starting training: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500

@t5_training_bp.route('/api/t5/train/<job_id>/status', methods=['GET'])
def get_training_status(job_id):
    """Get status of a training job"""
    try:
        if job_id not in training_jobs:
            return jsonify({'ok': False, 'error': 'Job not found'}), 404
        
        job = training_jobs[job_id]
        return jsonify({'ok': True, 'job': job})
        
    except Exception as e:
        logger.error(f"Error getting training status: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500

@t5_training_bp.route('/api/t5/deploy', methods=['POST'])
def deploy_model():
    """Deploy trained model to production"""
    try:
        data = request.json or {}
        job_id = data.get('job_id')
        
        if not job_id or job_id not in training_jobs:
            return jsonify({'ok': False, 'error': 'Invalid job ID'}), 400
        
        job = training_jobs[job_id]
        
        if job['status'] != 'completed':
            return jsonify({'ok': False, 'error': 'Training not completed'}), 400
        
        # Copy model to production checkpoint
        source = os.path.join(T5_BASE_DIR, 'trained/quick-fix/checkpoint-quick-fix')
        target = os.path.join(T5_BASE_DIR, 'trained/checkpoint-3')
        
        if not os.path.exists(source):
            return jsonify({'ok': False, 'error': 'Trained model not found'}), 404
        
        # Create backup of current model
        if os.path.exists(target):
            backup_name = f'checkpoint-3-backup-{datetime.now().strftime("%Y%m%d_%H%M%S")}'
            backup_path = os.path.join(T5_BASE_DIR, 'trained', backup_name)
            os.rename(target, backup_path)
        
        # Copy new model
        import shutil
        shutil.copytree(source, target)
        
        return jsonify({
            'ok': True,
            'message': 'Model deployed successfully',
            'deployed_at': datetime.now().isoformat(),
            'restart_required': True
        })
        
    except Exception as e:
        logger.error(f"Error deploying model: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500

@t5_training_bp.route('/api/t5/models', methods=['GET'])
def list_models():
    """List available trained models"""
    try:
        trained_dir = os.path.join(T5_BASE_DIR, 'trained')
        models = []
        
        if os.path.exists(trained_dir):
            for item in os.listdir(trained_dir):
                item_path = os.path.join(trained_dir, item)
                if os.path.isdir(item_path) and 'checkpoint' in item:
                    stat = os.stat(item_path)
                    models.append({
                        'name': item,
                        'path': item_path,
                        'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        'size_mb': sum(
                            os.path.getsize(os.path.join(dirpath, filename))
                            for dirpath, dirnames, filenames in os.walk(item_path)
                            for filename in filenames
                        ) / (1024 * 1024)
                    })
        
        return jsonify({'ok': True, 'models': sorted(models, key=lambda x: x['modified'], reverse=True)})
        
    except Exception as e:
        logger.error(f"Error listing models: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500
