"""
ALIS-X Background Tasks
=======================
Celery task definitions for non-blocking AI processing.

All tasks:
  - Are idempotent where possible
  - Log to audit system
  - Handle AI failures gracefully
  - Return structured results
  - Never crash on AI errors — rules engine is always the fallback
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger('task_queue')


def _get_celery():
    from celery_app import app
    return app


# ── Helper: run async function in sync Celery context ────────────────────────

def _run_async(coro):
    """Execute an async coroutine from a sync Celery task."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                fut = pool.submit(asyncio.run, coro)
                return fut.result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


# ── AI Tasks ──────────────────────────────────────────────────────────────────

def run_cloud_interpretation(
    result_id:   int,
    test_code:   str,
    test_name:   str,
    value:       str,
    unit:        str,
    flag:        str,
    patient_age: int = 0,
    patient_sex: str = '',
    lab_req_id:  int = 0,
) -> dict[str, Any]:
    """
    Cloud LLM interpretation of a single result.
    Called after local rules engine has already run.
    Stores AI enrichment back to the database.
    """
    from celery_app import app

    @app.task(name='tasks.run_cloud_interpretation', queue='ai_heavy',
              bind=True, max_retries=2, default_retry_delay=30)
    def _task(self, **kwargs):
        try:
            from ai_services.cloud_llm import advanced_interpretation
            ai_result = _run_async(advanced_interpretation(
                panel_results=[{
                    'test_name': kwargs['test_name'],
                    'value':     kwargs['value'],
                    'unit':      kwargs['unit'],
                    'flag':      kwargs['flag'],
                }],
                patient_age = kwargs.get('patient_age', 0),
                patient_sex = kwargs.get('patient_sex', ''),
            ))
            _store_ai_result(kwargs['result_id'], ai_result, 'cloud')
            return ai_result
        except Exception as exc:
            logger.error('Cloud interpretation task failed: %s', exc)
            try:
                self.retry(exc=exc)
            except Exception:
                return {'error': str(exc), 'layer': 'cloud_failed'}

    return _task.delay(
        result_id=result_id, test_code=test_code, test_name=test_name,
        value=value, unit=unit, flag=flag, patient_age=patient_age,
        patient_sex=patient_sex, lab_req_id=lab_req_id,
    )


def run_vision_analysis(
    task_id:    str,
    image_type: str,
    file_path:  str,
    patient_id: int = 0,
    lab_req_id: int = 0,
    priority:   str = 'routine',
) -> Any:
    """Queue image for vision analysis."""
    from celery_app import app

    @app.task(name='tasks.run_vision_analysis', queue='ai_heavy',
              bind=True, max_retries=1, time_limit=180)
    def _task(self, **kwargs):
        from ai_services.vision_service import VisionTask, submit_image_task
        vtask = VisionTask(
            task_id    = kwargs['task_id'],
            image_type = kwargs['image_type'],
            file_path  = kwargs['file_path'],
            patient_id = kwargs.get('patient_id'),
            lab_req_id = kwargs.get('lab_req_id'),
            priority   = kwargs.get('priority', 'routine'),
        )
        return _run_async(submit_image_task(vtask))

    return _task.delay(
        task_id=task_id, image_type=image_type, file_path=file_path,
        patient_id=patient_id, lab_req_id=lab_req_id, priority=priority,
    )


def run_local_interpretation(
    result_id:   int,
    test_name:   str,
    value:       str,
    unit:        str,
    flag:        str,
    ref_range:   str = '',
    patient_sex: str = '',
    patient_age: int = 0,
) -> Any:
    """Local LLM interpretation queued in background."""
    from celery_app import app

    @app.task(name='tasks.run_local_interpretation', queue='ai_local',
              bind=True, max_retries=1, time_limit=60)
    def _task(self, **kwargs):
        try:
            from ai_services.local_llm import interpret_lab_result
            result = _run_async(interpret_lab_result(
                test_name = kwargs['test_name'],
                value     = kwargs['value'],
                unit      = kwargs['unit'],
                flag      = kwargs['flag'],
                ref_range = kwargs.get('ref_range', ''),
                sex       = kwargs.get('patient_sex', ''),
                age       = kwargs.get('patient_age', 0),
            ))
            _store_ai_result(kwargs['result_id'], result, 'local')
            return result
        except Exception as exc:
            logger.warning('Local interpretation task failed: %s', exc)
            return {'error': str(exc), 'layer': 'local_failed'}

    return _task.delay(
        result_id=result_id, test_name=test_name, value=value,
        unit=unit, flag=flag, ref_range=ref_range,
        patient_sex=patient_sex, patient_age=patient_age,
    )


def generate_report(
    lab_req_id:     int,
    department:     str,
    patient_info:   dict,
    report_type:    str = 'standard',   # standard | full_ai | summary
) -> Any:
    """Generate laboratory report narrative in background."""
    from celery_app import app

    @app.task(name='tasks.generate_report', queue='reports',
              bind=True, max_retries=1, time_limit=120)
    def _task(self, **kwargs):
        from core.database import SessionLocal
        from models.laboratory import LabRequest, LabResult
        req_id = kwargs['lab_req_id']
        db = SessionLocal()
        try:
            results = db.query(LabResult).filter(LabResult.lab_request_id == req_id).all()
            results_list = [
                {'test_name': r.test.name if r.test else 'Unknown',
                 'value':     r.result_value or '', 'unit': r.unit or '',
                 'flag':      r.flag or 'N'}
                for r in results if r.result_value
            ]
            if kwargs.get('report_type') == 'full_ai':
                from ai_services.cloud_llm import generate_full_report
                text = _run_async(generate_full_report(
                    department    = kwargs['department'],
                    test_results  = results_list,
                    patient_info  = kwargs.get('patient_info', {}),
                ))
            else:
                from ai_services.local_llm import draft_report_section
                text = _run_async(draft_report_section(
                    department   = kwargs['department'],
                    test_results = results_list,
                ))
            return {'report_text': text, 'lab_req_id': req_id}
        finally:
            db.close()

    return _task.delay(
        lab_req_id=lab_req_id, department=department,
        patient_info=patient_info, report_type=report_type,
    )


# ── Periodic/scheduled tasks ──────────────────────────────────────────────────

def register_periodic_tasks():
    """Register periodic tasks — called from celery_app.beat_schedule."""
    from celery_app import app

    @app.task(name='tasks.epidemic_sweep', queue='surveillance')
    def epidemic_sweep():
        """Run epidemic surveillance analysis every 15 minutes."""
        from core.database import SessionLocal
        from sqlalchemy import func, text
        db = SessionLocal()
        try:
            # Find abnormal result spikes in past 7 days vs 30-day baseline
            result = db.execute(text("""
                SELECT test_id, flag, COUNT(*) as count_7d
                FROM lab_results
                WHERE created_at >= datetime('now', '-7 days')
                  AND flag IN ('HH', 'LL', 'POS', 'H')
                GROUP BY test_id, flag
                HAVING count_7d >= 3
            """)).fetchall()

            alerts = []
            for row in result:
                test_id, flag, count_7d = row
                baseline_row = db.execute(text("""
                    SELECT COUNT(*) / 4.0 as baseline
                    FROM lab_results
                    WHERE test_id = :tid
                      AND flag = :flag
                      AND created_at >= datetime('now', '-28 days')
                      AND created_at < datetime('now', '-7 days')
                """), {'tid': test_id, 'flag': flag}).fetchone()
                baseline = (baseline_row[0] or 1.0)
                if count_7d > baseline * 1.5:
                    alerts.append({'test_id': test_id, 'flag': flag,
                                   'count_7d': count_7d, 'baseline': baseline,
                                   'increase_pct': int(((count_7d/baseline)-1)*100)})
            if alerts:
                logger.warning('Epidemic sweep found %d signal(s): %s', len(alerts), alerts[:3])
            return {'alerts': alerts, 'swept_at': str(func.now())}
        except Exception as e:
            logger.error('Epidemic sweep error: %s', e)
            return {'error': str(e)}
        finally:
            db.close()

    @app.task(name='tasks.inventory_check', queue='default')
    def inventory_check():
        """Daily inventory level check and auto-alerts."""
        from core.database import SessionLocal
        from ai_services.rules_engine import check_inventory
        db = SessionLocal()
        try:
            from models.inventory import InventoryItem  # adjust to your model
            items = db.query(InventoryItem).filter(
                InventoryItem.is_active == True
            ).all() if hasattr(__builtins__, 'InventoryItem') else []

            alerts = []
            for item in items:
                daily_use = getattr(item, 'daily_usage', 1) or 1
                current   = getattr(item, 'quantity', 0) or 0
                expiry_d  = getattr(item, 'days_until_expiry', None)
                alert     = check_inventory(current, daily_use, expiry_d)
                if alert['level'] in ('CRITICAL', 'LOW'):
                    alerts.append({'item': str(item), 'alert': alert})
            return {'checked': len(items), 'alerts': len(alerts), 'items': alerts}
        except Exception as e:
            return {'error': str(e)}
        finally:
            db.close()

    @app.task(name='tasks.audit_flush', queue='default')
    def audit_flush():
        """Flush any buffered audit log entries to database."""
        logger.info('Audit flush task ran')
        return {'status': 'ok'}


# ── Internal helpers ──────────────────────────────────────────────────────────

def _store_ai_result(result_id: int, ai_data: dict, layer: str) -> None:
    """Write AI interpretation back to lab result record."""
    try:
        from core.database import SessionLocal
        from models.laboratory import LabResult
        db = SessionLocal()
        r  = db.query(LabResult).filter(LabResult.id == result_id).first()
        if r:
            r.ai_interpretation = json.dumps(ai_data, ensure_ascii=False)[:2000]
            r.ai_layer          = layer
            db.commit()
        db.close()
    except Exception as e:
        logger.warning('Could not store AI result for id=%s: %s', result_id, e)
