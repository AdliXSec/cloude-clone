"""Antrean tagihan berbasis database. Dipakai API (enqueue) dan worker (process)."""
from datetime import datetime, timezone

from sqlalchemy import update

from kosanhub import db
from kosanhub.errors import ConflictError, ValidationError
from kosanhub.models import BillingJob, Contract
from kosanhub.services.billing import create_bill


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def enqueue_billing_job(year, month):
    if not 1 <= month <= 12:
        raise ValidationError("month harus 1-12")
    if year < 2000 or year > 2100:
        raise ValidationError("year di luar rentang yang wajar")
    job = BillingJob(period_year=year, period_month=month, status=BillingJob.PENDING)
    db.session.add(job)
    return job


def claim_next_job():
    """Ambil job PENDING tertua secara atomik, aman bila ada lebih dari satu worker."""
    # Tutup transaksi lama dulu: di MySQL (REPEATABLE READ) transaksi yang dibiarkan terbuka
    # membuat worker terus melihat snapshot lama sehingga job baru tidak pernah terlihat.
    db.session.rollback()
    candidate_ids = db.session.scalars(
        db.select(BillingJob.id)
        .where(BillingJob.status == BillingJob.PENDING)
        .order_by(BillingJob.id)
        .limit(5)
    ).all()
    for job_id in candidate_ids:
        result = db.session.execute(
            update(BillingJob)
            .where(BillingJob.id == job_id, BillingJob.status == BillingJob.PENDING)
            .values(status=BillingJob.PROCESSING, started_at=_now())
        )
        db.session.commit()
        if result.rowcount == 1:
            return db.session.get(BillingJob, job_id)
    db.session.rollback()
    return None


def process_job(job, due_day=10):
    """Terbitkan tagihan semua kontrak yang berlaku di periode job. Idempoten per kontrak."""
    created = skipped = 0
    try:
        contracts = db.session.scalars(
            db.select(Contract).where(Contract.status == Contract.ACTIVE).order_by(Contract.id)
        ).all()
        for contract in contracts:
            try:
                create_bill(contract, job.period_year, job.period_month, due_day=due_day)
                created += 1
            except (ConflictError, ValidationError):
                # sudah pernah ditagih / kontrak belum atau tidak lagi berlaku di periode ini
                skipped += 1
        job.created_count = created
        job.skipped_count = skipped
        job.status = BillingJob.COMPLETED
        job.error = None
    except Exception as exc:  # noqa: BLE001 - worker tidak boleh mati karena satu job
        db.session.rollback()
        job = db.session.get(BillingJob, job.id)
        job.status = BillingJob.FAILED
        job.error = str(exc)[:1000]
    job.finished_at = _now()
    db.session.commit()
    return job
