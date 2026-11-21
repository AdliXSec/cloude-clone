"""Endpoint antrean job tagihan bulanan (diproses oleh container worker)."""
from datetime import date

from flask import Blueprint, jsonify, request

from kosanhub import db
from kosanhub.errors import NotFoundError
from kosanhub.models import BillingJob
from kosanhub.services.jobs import enqueue_billing_job
from kosanhub.utils import parse_int

jobs_bp = Blueprint("jobs", __name__)


@jobs_bp.post("/generate-bills")
def generate_bills():
    data = request.get_json(silent=True) or {}
    today = date.today()
    job = enqueue_billing_job(
        parse_int(data.get("year", today.year), "year"),
        parse_int(data.get("month", today.month), "month"),
    )
    db.session.commit()
    return jsonify(job.to_dict()), 202


@jobs_bp.get("")
def list_jobs():
    jobs = db.session.scalars(db.select(BillingJob).order_by(BillingJob.id.desc()).limit(50)).all()
    return jsonify([j.to_dict() for j in jobs])


@jobs_bp.get("/<int:job_id>")
def get_job(job_id):
    job = db.session.get(BillingJob, job_id)
    if job is None:
        raise NotFoundError("Job tidak ditemukan")
    return jsonify(job.to_dict())
