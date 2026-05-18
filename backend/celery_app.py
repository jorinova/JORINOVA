"""
ALIS-X Celery Application
=========================
Background task queue for non-blocking AI and lab processing.
Redis is used as both broker and result backend.

Queues:
  - default      : general tasks
  - ai_heavy     : cloud LLM, vision analysis (low priority)
  - ai_local     : local LLM tasks (medium priority)
  - reports      : report generation, export
  - surveillance : epidemic monitoring (scheduled)

Usage:
  # Start worker
  celery -A celery_app worker --loglevel=info -Q default,ai_local,reports
  celery -A celery_app worker --loglevel=info -Q ai_heavy --concurrency=1

  # Start beat scheduler (for periodic tasks)
  celery -A celery_app beat --loglevel=info
"""
import os
import sys
from pathlib import Path

# Ensure backend directory is on path
sys.path.insert(0, str(Path(__file__).parent))

from celery import Celery
from celery.schedules import crontab

# ── Celery configuration ──────────────────────────────────────────────────────

REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

app = Celery('alis_x', broker=REDIS_URL, backend=REDIS_URL)

app.conf.update(
    # Serialization
    task_serializer         = 'json',
    result_serializer       = 'json',
    accept_content          = ['json'],
    task_compression        = 'gzip',

    # Routing
    task_default_queue      = 'default',
    task_queues             = {
        'default':     {'exchange': 'default'},
        'ai_heavy':    {'exchange': 'ai_heavy'},
        'ai_local':    {'exchange': 'ai_local'},
        'reports':     {'exchange': 'reports'},
        'surveillance':{'exchange': 'surveillance'},
    },
    task_routes             = {
        'tasks.run_cloud_interpretation':  {'queue': 'ai_heavy'},
        'tasks.run_vision_analysis':       {'queue': 'ai_heavy'},
        'tasks.run_local_interpretation':  {'queue': 'ai_local'},
        'tasks.generate_report':           {'queue': 'reports'},
        'tasks.epidemic_sweep':            {'queue': 'surveillance'},
        'tasks.inventory_check':           {'queue': 'default'},
        'tasks.audit_flush':               {'queue': 'default'},
    },

    # Performance (CPU-friendly settings for pilot deployment)
    worker_prefetch_multiplier  = 1,     # one task at a time for AI workers
    task_acks_late              = True,  # ack after completion, not receipt
    worker_max_tasks_per_child  = 50,    # restart worker after 50 tasks (memory)
    task_time_limit             = 120,   # hard limit: 2 min per task
    task_soft_time_limit        = 90,    # soft limit: graceful cancel at 90s
    result_expires              = 3600,  # results kept for 1 hour

    # Beat schedule (periodic tasks)
    beat_schedule = {
        'epidemic-sweep-every-15min': {
            'task':     'tasks.epidemic_sweep',
            'schedule': crontab(minute='*/15'),
        },
        'inventory-check-daily': {
            'task':     'tasks.inventory_check',
            'schedule': crontab(hour=7, minute=0),
        },
        'audit-flush-hourly': {
            'task':     'tasks.audit_flush',
            'schedule': crontab(minute=0),
        },
    },
)
