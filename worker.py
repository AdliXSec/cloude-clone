#!/usr/bin/env python
"""
Background worker: loop polling antrean tagihan dari database dan memproses.
Dijalankan sebagai container terpisah di compose.yaml.
"""
import logging
import sys
import time

from kosanhub import create_app, db
from kosanhub.services.jobs import claim_next_job, process_job

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = create_app()


def main():
    with app.app_context():
        logger.info("KosanHub Worker: siap memproses antrean tagihan")
        poll_seconds = app.config["WORKER_POLL_SECONDS"]
        while True:
            try:
                job = claim_next_job()
                if job:
                    logger.info(f"Memproses job #{job.id} periode {job.period_year:04d}-{job.period_month:02d}")
                    process_job(job, due_day=app.config["BILL_DUE_DAY"])
                    logger.info(f"Job #{job.id} selesai: {job.created_count} tagihan dibuat, {job.skipped_count} dilewati")
            except Exception as exc:  # noqa: BLE001
                logger.exception(f"Error processing job: {exc}")
                db.session.rollback()
            time.sleep(poll_seconds)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Worker dihentikan")
        sys.exit(0)
