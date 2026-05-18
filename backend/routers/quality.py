"""Quality Management router — IQC, EQA, SOP, NCR, CAPA, ISO 15189."""
from typing import Optional
from datetime import date as date_t, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from pydantic import BaseModel
from core.database import get_db
from core.security import get_current_user
from models.user import User
from models.quality import IQCResult, EQAResult, SOP, NCR, CAPA

router = APIRouter(prefix='/quality', tags=['Quality'])


def _ncr_num(db): year=date_t.today().year; n=db.query(NCR).filter(NCR.ncr_number.like(f'NCR-{year}-%')).count(); return f'NCR-{year}-{str(n+1).zfill(4)}'
def _capa_num(db): year=date_t.today().year; n=db.query(CAPA).filter(CAPA.capa_number.like(f'CAPA-{year}-%')).count(); return f'CAPA-{year}-{str(n+1).zfill(4)}'
def _sop_num(db): n=db.query(SOP).count(); return f'SOP-LAB-{str(n+1).zfill(3)}'


@router.get('/dashboard')
def dashboard(db: Session=Depends(get_db), _u: User=Depends(get_current_user)):
    from datetime import timedelta
    today = date_t.today()
    since30 = today - timedelta(days=30)
    total_iqc = db.query(IQCResult).filter(IQCResult.run_date>=since30).count()
    pass_iqc  = db.query(IQCResult).filter(IQCResult.run_date>=since30, IQCResult.status=='PASS').count()
    return {
        'iqc_pass_rate': round((pass_iqc/total_iqc*100) if total_iqc else 100, 1),
        'ncr_open': db.query(NCR).filter(NCR.status.in_(['OPEN','INVESTIGATION'])).count(),
        'capa_in_progress': db.query(CAPA).filter(CAPA.status.in_(['OPEN','IN_PROGRESS'])).count(),
        'sop_due_review': db.query(SOP).filter(SOP.review_date<=today, SOP.status=='CURRENT').count(),
        'eqa_pending': db.query(EQAResult).filter(EQAResult.status=='PENDING').count(),
        'iqc_violations_today': db.query(IQCResult).filter(IQCResult.run_date==today, IQCResult.status.in_(['WARN','REJECT'])).count(),
    }


# ── IQC ──────────────────────────────────────────────────────────
@router.get('/iqc')
def list_iqc(department: Optional[str]=None, analyte: Optional[str]=None,
             date_from: Optional[str]=None, date_to: Optional[str]=None,
             status: Optional[str]=None, skip: int=0, limit: int=200,
             db: Session=Depends(get_db), _u: User=Depends(get_current_user)):
    q = db.query(IQCResult)
    if department: q=q.filter(IQCResult.department==department)
    if analyte:    q=q.filter(IQCResult.analyte_code==analyte.upper())
    if date_from:  q=q.filter(IQCResult.run_date>=date_from)
    if date_to:    q=q.filter(IQCResult.run_date<=date_to)
    if status:     q=q.filter(IQCResult.status==status)
    return q.order_by(desc(IQCResult.run_date), desc(IQCResult.created_at)).offset(skip).limit(limit).all()


@router.post('/iqc', status_code=201)
def create_iqc(
    department: str, analyte_code: str, analyte_name: str,
    control_level: str, target_mean: float, sd: float, result_value: float,
    unit: Optional[str]=None, lot_number: Optional[str]=None,
    analyzer_name: Optional[str]=None, run_date: Optional[str]=None,
    db: Session=Depends(get_db), user: User=Depends(get_current_user),
):
    z = round((result_value-target_mean)/sd, 3) if sd else 0
    abs_z = abs(z)
    if abs_z > 3:   status, rule = 'REJECT', '1_3s'
    elif abs_z > 2: status, rule = 'WARN', '1_2s'
    else:           status, rule = 'PASS', 'PASS'
    rec = IQCResult(
        department=department, analyte_code=analyte_code.upper(),
        analyte_name=analyte_name, control_level=control_level,
        lot_number=lot_number, target_mean=target_mean, sd=sd,
        result_value=result_value, unit=unit, z_score=z,
        westgard_rule=rule, status=status, analyzer_name=analyzer_name,
        operator_id=user.id, operator_name=f'{user.first_name} {user.last_name}'.strip() or user.username,
        run_date=date_t.fromisoformat(run_date) if run_date else date_t.today(),
    )
    db.add(rec); db.commit(); db.refresh(rec)
    return {'id':rec.id,'z_score':z,'status':status,'westgard_rule':rule}


# ── Levey-Jennings + Full Westgard ───────────────────────────────

def _full_westgard(runs: list) -> list:
    """
    Apply all 6 Westgard rules to a list of z-scores (float).
    Returns list of {rule, index, description, action} violations.

    Rules (CLIA/Westgard Foundation):
      1-2s  WARNING  : single point > ±2 SD        — warn only
      1-3s  REJECT   : single point > ±3 SD        — reject run
      2-2s  REJECT   : 2 consecutive > same ±2 SD  — reject run
      R-4s  REJECT   : range between 2 consec > 4 SD (one +2s, next −2s or vice versa)
      4-1s  REJECT   : 4 consecutive same side > ±1 SD
      10x   REJECT   : 10 consecutive same side of mean
    """
    violations = []
    z = runs   # list of z-scores, index 0 = oldest

    for i, zi in enumerate(z):
        # 1-3s
        if abs(zi) > 3:
            violations.append({'rule':'1-3s','index':i,'severity':'REJECT',
                'description':f'Point {i+1}: z={zi:.2f} exceeds ±3 SD',
                'action':'Reject run. Investigate QC material, reagent lot, or instrument.'})
        # 1-2s
        elif abs(zi) > 2:
            violations.append({'rule':'1-2s','index':i,'severity':'WARN',
                'description':f'Point {i+1}: z={zi:.2f} exceeds ±2 SD',
                'action':'Warning. Check adjacent rules before accepting run.'})

        # 2-2s
        if i >= 1 and abs(zi) >= 2 and abs(z[i-1]) >= 2:
            if (zi > 0) == (z[i-1] > 0):   # same side
                violations.append({'rule':'2-2s','index':i,'severity':'REJECT',
                    'description':f'Points {i} and {i+1}: two consecutive > ±2 SD on same side',
                    'action':'Reject run. Systematic error suspected (calibration drift).'})

        # R-4s
        if i >= 1:
            rng = abs(zi - z[i-1])
            if rng > 4:
                violations.append({'rule':'R-4s','index':i,'severity':'REJECT',
                    'description':f'Points {i} and {i+1}: range={rng:.2f} SD (> 4 SD)',
                    'action':'Reject run. Random error suspected (pipetting, mixing).'})

        # 4-1s
        if i >= 3:
            last4 = z[i-3:i+1]
            if all(v > 1 for v in last4) or all(v < -1 for v in last4):
                violations.append({'rule':'4-1s','index':i,'severity':'REJECT',
                    'description':f'Points {i-2}–{i+1}: four consecutive > ±1 SD same side',
                    'action':'Reject run. Systematic bias — check calibration or reagents.'})

        # 10x
        if i >= 9:
            last10 = z[i-9:i+1]
            if all(v > 0 for v in last10) or all(v < 0 for v in last10):
                violations.append({'rule':'10x','index':i,'severity':'REJECT',
                    'description':f'Points {i-8}–{i+1}: ten consecutive same side of mean',
                    'action':'Reject run. Systematic drift — recalibrate, check reagent lot.'})

    return violations


@router.get('/iqc/levey-jennings')
def levey_jennings(
    department:    str,
    analyte_code:  str,
    control_level: str       = 'L1',
    days:          int       = 30,
    db:            Session   = Depends(get_db),
    _u:            User      = Depends(get_current_user),
):
    """
    Return all data needed to render a Levey-Jennings chart for one
    analyte / control level, with full Westgard multi-rule analysis.

    Response:
      points    — [{date, value, z_score, status, westgard_rule, run_date}]
      stats     — {mean, sd, cv_pct, n, pass_rate}
      westgard  — [{rule, index, severity, description, action}]
      run_decision — ACCEPT | WARN | REJECT
      sd_lines  — {plus1, plus2, plus3, minus1, minus2, minus3}
    """
    from datetime import timedelta
    since = date_t.today() - timedelta(days=days)

    rows = (db.query(IQCResult)
            .filter(IQCResult.department    == department,
                    IQCResult.analyte_code  == analyte_code.upper(),
                    IQCResult.control_level == control_level,
                    IQCResult.run_date      >= since)
            .order_by(IQCResult.run_date, IQCResult.created_at)
            .all())

    if not rows:
        return {'points':[],'stats':{},'westgard':[],'run_decision':'NO_DATA','sd_lines':{}}

    mean = rows[0].target_mean
    sd   = rows[0].sd
    n    = len(rows)
    vals = [r.result_value for r in rows]

    # Recalculate z-scores from stored data for consistency
    z_scores = [(v - mean) / sd if sd else 0.0 for v in vals]

    # Pass/fail count
    passed = sum(1 for r in rows if r.status == 'PASS')

    # Full Westgard
    violations = _full_westgard(z_scores)
    any_reject = any(v['severity'] == 'REJECT' for v in violations)
    any_warn   = any(v['severity'] == 'WARN'   for v in violations)
    decision   = 'REJECT' if any_reject else 'WARN' if any_warn else 'ACCEPT'

    # CV%
    actual_mean = sum(vals)/n if n else mean
    actual_sd   = (sum((v-actual_mean)**2 for v in vals)/n)**0.5 if n > 1 else sd
    cv_pct = round(actual_sd / actual_mean * 100, 2) if actual_mean else 0

    points = [{
        'id':          r.id,
        'run_date':    str(r.run_date),
        'value':       r.result_value,
        'z_score':     round(z_scores[i], 3),
        'status':      r.status,
        'westgard_rule': r.westgard_rule,
        'operator':    r.operator_name,
        'analyzer':    r.analyzer_name,
        'lot':         r.lot_number,
    } for i, r in enumerate(rows)]

    return {
        'analyte':      analyte_code.upper(),
        'department':   department,
        'control_level':control_level,
        'period_days':  days,
        'unit':         rows[0].unit if rows else '',
        'points':       points,
        'stats': {
            'target_mean': mean, 'target_sd': sd,
            'actual_mean': round(actual_mean, 3),
            'actual_sd':   round(actual_sd, 3),
            'cv_pct':      cv_pct,
            'n':           n,
            'pass_rate':   round(passed / n * 100, 1) if n else 100,
            'violations':  len(violations),
        },
        'westgard':      violations,
        'run_decision':  decision,
        'sd_lines': {
            'mean':   mean,
            'plus1':  round(mean + sd, 3),  'minus1': round(mean - sd, 3),
            'plus2':  round(mean + 2*sd,3), 'minus2': round(mean - 2*sd,3),
            'plus3':  round(mean + 3*sd,3), 'minus3': round(mean - 3*sd,3),
        },
    }


@router.get('/iqc/analytes')
def list_iqc_analytes(
    department: Optional[str] = None,
    db: Session = Depends(get_db),
    _u: User    = Depends(get_current_user),
) -> list:
    """Distinct analytes with IQC data — for dropdown selection in LJ chart."""
    q = db.query(IQCResult.analyte_code, IQCResult.analyte_name,
                 IQCResult.department, IQCResult.unit).distinct()
    if department: q = q.filter(IQCResult.department == department)
    return [{'code':r[0],'name':r[1],'department':r[2],'unit':r[3]} for r in q.all()]


# ── EQA ──────────────────────────────────────────────────────────
@router.get('/eqa')
def list_eqa(scheme: Optional[str]=None, status: Optional[str]=None,
             skip: int=0, limit: int=50,
             db: Session=Depends(get_db), _u: User=Depends(get_current_user)):
    q = db.query(EQAResult)
    if scheme: q=q.filter(EQAResult.scheme==scheme)
    if status: q=q.filter(EQAResult.status==status)
    return q.order_by(desc(EQAResult.created_at)).offset(skip).limit(limit).all()


@router.post('/eqa', status_code=201)
def create_eqa(
    scheme: str, cycle: str, department: str, analyte: str,
    your_result: Optional[float]=None, target_value: Optional[float]=None,
    unit: Optional[str]=None, sdi: Optional[float]=None,
    score: Optional[float]=None, method: Optional[str]=None,
    db: Session=Depends(get_db), user: User=Depends(get_current_user),
):
    status = 'PENDING' if score is None else ('PASSED' if score>=80 else ('BORDERLINE' if score>=70 else 'FAILED'))
    rec = EQAResult(scheme=scheme, cycle=cycle, department=department, analyte=analyte,
                    your_result=your_result, target_value=target_value, unit=unit,
                    sdi=sdi, score=score, method=method, status=status, submitted_by_id=user.id)
    db.add(rec); db.commit(); db.refresh(rec)
    return rec


# ── SOPs ─────────────────────────────────────────────────────────
@router.get('/sop')
def list_sops(department: Optional[str]=None, status: Optional[str]=None,
              skip: int=0, limit: int=100,
              db: Session=Depends(get_db), _u: User=Depends(get_current_user)):
    q = db.query(SOP)
    if department: q=q.filter(SOP.department==department)
    if status:     q=q.filter(SOP.status==status)
    return q.order_by(SOP.sop_number).offset(skip).limit(limit).all()


@router.post('/sop', status_code=201)
def create_sop(
    title: str, department: str, version: str='v1.0',
    effective_date: Optional[str]=None, review_date: Optional[str]=None,
    author: Optional[str]=None, approved_by: Optional[str]=None,
    scope: Optional[str]=None,
    db: Session=Depends(get_db), user: User=Depends(get_current_user),
):
    sop_num = _sop_num(db)
    rec = SOP(sop_number=sop_num, title=title, department=department, version=version,
              effective_date=date_t.fromisoformat(effective_date) if effective_date else None,
              review_date=date_t.fromisoformat(review_date) if review_date else None,
              author=author, approved_by=approved_by, approved_by_id=user.id, scope=scope)
    db.add(rec); db.commit(); db.refresh(rec)
    return rec


# ── NCR ──────────────────────────────────────────────────────────
@router.get('/ncr')
def list_ncr(status: Optional[str]=None, severity: Optional[str]=None,
             skip: int=0, limit: int=50,
             db: Session=Depends(get_db), _u: User=Depends(get_current_user)):
    q = db.query(NCR)
    if status:   q=q.filter(NCR.status==status)
    if severity: q=q.filter(NCR.severity==severity)
    return q.order_by(desc(NCR.created_at)).offset(skip).limit(limit).all()


@router.post('/ncr', status_code=201)
def create_ncr(
    ncr_type: str, department: str, severity: str, description: str,
    immediate_action: Optional[str]=None, capa_required: bool=False,
    reported_by: Optional[str]=None,
    db: Session=Depends(get_db), user: User=Depends(get_current_user),
):
    rec = NCR(ncr_number=_ncr_num(db), ncr_type=ncr_type, department=department,
              severity=severity, description=description, immediate_action=immediate_action,
              capa_required=capa_required, reported_by_id=user.id,
              reported_by=reported_by or f'{user.first_name} {user.last_name}'.strip())
    db.add(rec); db.commit(); db.refresh(rec)
    return rec


@router.patch('/ncr/{nid}/close')
def close_ncr(nid: int, db: Session=Depends(get_db), _u: User=Depends(get_current_user)):
    r = db.query(NCR).filter(NCR.id==nid).first()
    if not r: raise HTTPException(404,'NCR not found')
    r.status='CLOSED'; r.closed_at=datetime.now(timezone.utc)
    db.commit(); return {'status':'closed'}


# ── CAPA ─────────────────────────────────────────────────────────
@router.get('/capa')
def list_capa(status: Optional[str]=None, skip: int=0, limit: int=50,
              db: Session=Depends(get_db), _u: User=Depends(get_current_user)):
    q = db.query(CAPA)
    if status: q=q.filter(CAPA.status==status)
    return q.order_by(desc(CAPA.created_at)).offset(skip).limit(limit).all()


@router.post('/capa', status_code=201)
def create_capa(
    capa_type: str, description: str, ncr_id: Optional[int]=None,
    root_cause: Optional[str]=None, assigned_to: Optional[str]=None,
    target_date: Optional[str]=None, effectiveness_criteria: Optional[str]=None,
    db: Session=Depends(get_db), user: User=Depends(get_current_user),
):
    rec = CAPA(capa_number=_capa_num(db), capa_type=capa_type, ncr_id=ncr_id,
               description=description, root_cause=root_cause, assigned_to=assigned_to,
               assigned_to_id=user.id, effectiveness_criteria=effectiveness_criteria,
               target_date=date_t.fromisoformat(target_date) if target_date else None)
    db.add(rec); db.commit(); db.refresh(rec)
    return rec
