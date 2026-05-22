"""
BOOTSTRAP seed for the training-demo system.

PRODUCTION RULE:
    The training/demo system runs on REAL pilot data.
    When a pilot site is live, this script SHOULD NOT BE RUN.
    Each scene's `liveData` comes from the pilot DB via /api/v1/training/data-source/...
    Scenes show a "Waiting for pilot data" empty state when no record is bound.

When this script IS useful:
    - Local development before any pilot data has been entered
    - QA on a fresh DB
    - First-run installation before any analyzer or clinician has touched the system

The script is idempotent: re-running it does not create duplicates. It is also
deliberately small (one record per entity) so removing the rows is trivial.

Run:
    cd backend
    ../.venv/Scripts/python.exe -m scripts.seed_training_pilot
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timedelta, timezone

# Make package imports work when run as `python -m scripts.seed_training_pilot`
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import SessionLocal, engine, Base
from models.patient   import Patient
from models.laboratory import LabRequest, LabResult
from models.blood_bank import BloodBag, CrossmatchRecord
from models.billing    import BillingRecord, BillingItem
from models.molecular  import PCRResult


def ensure_tables() -> None:
    Base.metadata.create_all(engine)


def upsert_patient(db) -> Patient:
    p = db.query(Patient).filter(Patient.pid == 'P-PILOT-0001').first()
    if p:
        return p
    p = Patient(
        pid           = 'P-PILOT-0001',
        unique_lab_id = 'RW-PILOT01',
        family_name   = 'Uwineza',
        other_names   = 'Mary',
        date_of_birth = date(1990, 6, 3),
        gender        = 'F',
        phone         = '+250788123456',
        is_active     = True,
    )
    db.add(p)
    db.flush()
    return p


def upsert_lab_request(db, patient: Patient) -> LabRequest:
    lr = (db.query(LabRequest)
            .filter(LabRequest.lab_id == 'LR-PILOT-0001')
            .first())
    if lr:
        # Make sure key fields are still set the way the training scenes expect
        lr.emergency_level = 'stat'
        lr.doctor_name     = 'Dr. Kayitesi'
        lr.ward            = 'Maternity'
        return lr
    lr = LabRequest(
        lab_id          = 'LR-PILOT-0001',
        patient_id      = patient.id,
        pid             = patient.pid,
        lid             = patient.unique_lab_id,
        doctor_name     = 'Dr. Kayitesi',
        ward            = 'Maternity',
        diagnosis       = 'Routine antenatal panel, gestational week 28',
        emergency_level = 'stat',
        status          = 'received',
    )
    db.add(lr)
    db.flush()
    return lr


def seed_lab_results(db, lr: LabRequest, patient: Patient) -> int:
    """Pre-create LabResult rows for HGB, RBC, WBC (flagged H), PLT."""
    # Idempotency: skip if any results already exist for this lr
    existing = db.query(LabResult).filter(LabResult.lab_request_id == lr.id).count()
    if existing > 0:
        # Make sure WBC stays flagged for the critical_cbc demo
        wbc = (db.query(LabResult)
                 .filter(LabResult.lab_request_id == lr.id, LabResult.test_id == 3)
                 .first())
        if wbc:
            wbc.flag = 'H'
            wbc.value = '15000'
            wbc.numeric_value = 15000.0
            wbc.unit = 'cells/uL'
        return 0

    rows = [
        # (test_id, value, num, unit, flag)
        (1, '13.8',  13.8,    'g/dL',     None),   # HGB
        (2, '4.5',   4.5,     '10^6/uL',  None),   # RBC
        (3, '15000', 15000.0, 'cells/uL', 'H'),    # WBC — flagged
        (4, '240',   240.0,   'k/uL',     None),   # PLT
    ]
    created = 0
    for (tid, val, num, unit, flag) in rows:
        db.add(LabResult(
            lab_request_id = lr.id,
            test_id        = tid,
            pid            = patient.pid,
            lid            = patient.unique_lab_id,
            value          = val,
            numeric_value  = num,
            unit           = unit,
            flag           = flag,
            status         = 'PENDING',
        ))
        created += 1
    return created


def upsert_blood_bag(db, patient: Patient) -> BloodBag:
    bag = db.query(BloodBag).filter(BloodBag.bag_number == 'BB-PILOT-0001').first()
    if bag:
        return bag
    bag = BloodBag(
        bag_number       = 'BB-PILOT-0001',
        component        = 'PRBC',
        blood_group      = 'O+',
        volume_ml        = 350,
        status           = 'available',
        collection_date  = date.today() - timedelta(days=12),
        expiry_date      = date.today() + timedelta(days=18),
        is_irradiated    = False,
        is_leukoreduced  = True,
    )
    db.add(bag)
    db.flush()
    db.add(CrossmatchRecord(
        blood_bag_id = bag.id,
        patient_id   = patient.id,
        result       = 'compatible',
        method       = 'Indirect Antiglobulin Test (IAT)',
        ai_flag      = False,
    ))
    return bag


def upsert_billing(db, lr: LabRequest, patient: Patient) -> BillingRecord:
    br = (db.query(BillingRecord)
            .filter(BillingRecord.lab_request_id == lr.id)
            .first())
    if br:
        return br
    br = BillingRecord(
        lab_request_id = lr.id,
        patient_id     = patient.id,
        status         = 'CONFIRMED',
        currency       = 'RWF',
        subtotal_amount= 15500.0,
        discount_amount= 0.0,
        total_amount   = 15500.0,
        paid_amount    = 15500.0,
        payment_method = 'MOMO',
        momo_ref       = 'MTN-7842-3091',
    )
    db.add(br)
    db.flush()
    items = [
        ('CBC',   'Complete Blood Count',           1, 5500.0,  5500.0),
        ('BMP',   'Basic Metabolic Panel',          1, 8500.0,  8500.0),
        ('CREAT', 'Creatinine',                     1, 1500.0,  1500.0),
    ]
    for code, name, qty, unit_price, total in items:
        db.add(BillingItem(
            billing_record_id = br.id,
            lab_request_id    = lr.id,
            item_code         = code,
            item_name         = name,
            quantity          = qty,
            unit_price        = unit_price,
            total_price       = total,
        ))
    return br


def upsert_pcr(db, lr: LabRequest, patient: Patient) -> PCRResult:
    pcr = db.query(PCRResult).filter(PCRResult.pcr_id == 'PCR-PILOT-0001').first()
    if pcr:
        return pcr
    pcr = PCRResult(
        pcr_id                 = 'PCR-PILOT-0001',
        lab_request_id         = lr.id,
        patient_id             = patient.id,
        pid                    = patient.pid,
        lid                    = patient.unique_lab_id,
        pcr_category           = 'TB',
        test_name              = 'GeneXpert MTB/RIF Ultra',
        target_organism        = 'Mycobacterium tuberculosis',
        instrument             = 'GeneXpert',
        cartridge_type         = 'Ultra',
        result                 = 'DETECTED',
        ct_value               = 22.4,
        semi_quant             = 'MEDIUM',
        rifampicin_resistance  = 'NOT_DETECTED',
        resistance_markers     = {'INH': 'S', 'RIF': 'S', 'PZA': 'S', 'EMB': 'S'},
        status                 = 'VALIDATED',
    )
    db.add(pcr)
    db.flush()
    return pcr


def main() -> None:
    ensure_tables()
    db = SessionLocal()
    try:
        patient = upsert_patient(db)
        lr      = upsert_lab_request(db, patient)
        n_res   = seed_lab_results(db, lr, patient)
        bag     = upsert_blood_bag(db, patient)
        br      = upsert_billing(db, lr, patient)
        pcr     = upsert_pcr(db, lr, patient)
        db.commit()
        print(f'Seed complete:')
        print(f'  patient        #{patient.id}  pid={patient.pid}')
        print(f'  lab_request    #{lr.id}       lab_id={lr.lab_id}  priority={lr.emergency_level}')
        print(f'  lab_results    {n_res} new (existing kept)')
        print(f'  blood_bag      #{bag.id}      number={bag.bag_number}')
        print(f'  billing_record #{br.id}       total={br.total_amount} {br.currency}  method={br.payment_method}')
        print(f'  pcr_result     #{pcr.id}      pcr_id={pcr.pcr_id}  result={pcr.result}')
    finally:
        db.close()


if __name__ == '__main__':
    main()
