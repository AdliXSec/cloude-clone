"""Test suite lengkap KosanHub untuk Pytest."""
from datetime import date
import pytest

from kosanhub import create_app, db
from kosanhub.config import TestingConfig
from kosanhub.models import Property, Room, Tenant, Contract, Bill, BillingJob, User, BookingRequest
from kosanhub.services.bookings import submit_booking, approve_booking, reject_booking, lookup_status
from werkzeug.security import generate_password_hash
import base64
from kosanhub.services.billing import prorated_amount, late_fee_percent, days_late, late_fee_amount, due_date_for
from kosanhub.services.contracts import create_contract, pay_bill
from kosanhub.services.jobs import claim_next_job, process_job
from kosanhub.errors import ConflictError, ValidationError


@pytest.fixture
def app():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


ADMIN_EMAIL = "admin@test.com"
ADMIN_PW = "rahasia-123"


@pytest.fixture
def admin(app):
    user = User(email=ADMIN_EMAIL, password_hash=generate_password_hash(ADMIN_PW))
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def basic(admin):
    """Header HTTP Basic untuk klien API (curl -u / Jenkins)."""
    token = base64.b64encode(f"{ADMIN_EMAIL}:{ADMIN_PW}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


@pytest.fixture
def adminc(app, admin):
    """Browser yang sudah login sebagai admin (session)."""
    c = app.test_client()
    res = c.post("/login", data={"email": ADMIN_EMAIL, "password": ADMIN_PW})
    assert res.status_code == 302
    return c


def csrf_of(c, path="/status"):
    """Ambil token CSRF session dengan membuka halaman yang merender form."""
    assert c.get(path).status_code == 200
    with c.session_transaction() as sess:
        return sess["csrf"]


@pytest.fixture
def seed_data(app):
    prop = Property(name="Kos Sejahtera", address="Jl. Sukabirus No. 1")
    db.session.add(prop)
    db.session.flush()

    room1 = Room(property_id=prop.id, number="101", monthly_price=1000000)
    room2 = Room(property_id=prop.id, number="102", monthly_price=800000)
    db.session.add_all([room1, room2])
    db.session.flush()

    tenant1 = Tenant(name="Adli", phone="081234567890", email="adli@example.com")
    tenant2 = Tenant(name="Noval", phone="089876543210", email="noval@example.com")
    db.session.add_all([tenant1, tenant2])
    db.session.commit()

    return {"prop": prop, "room1": room1, "room2": room2, "tenant1": tenant1, "tenant2": tenant2}


# ==========================================
# TEST 1: Healthcheck endpoint (Wajib tubes)
# ==========================================
def test_health_endpoint(client):
    res = client.get("/health")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"


# ==========================================
# TEST 2: Aturan Bisnis 1 (1 Kamar = 1 Kontrak Aktif)
# ==========================================
def test_rule_1_room_single_active_contract(app, seed_data):
    room1 = seed_data["room1"]
    tenant1 = seed_data["tenant1"]
    tenant2 = seed_data["tenant2"]

    # Kontrak pertama sukses
    c1 = create_contract(room1.id, tenant1.id, date(2026, 11, 1))
    db.session.commit()
    assert c1.status == Contract.ACTIVE

    # Kontrak kedua di kamar yang sama harus ditolak (ConflictError)
    with pytest.raises(ConflictError):
        create_contract(room1.id, tenant2.id, date(2026, 11, 5))


# ==========================================
# TEST 3: Aturan Bisnis 2 (Prorata Bulan Pertama)
# ==========================================
def test_rule_2_prorated_first_month(app):
    # Misal masuk 15 November 2026 (November ada 30 hari).
    # Sisa hari = 30 - 15 + 1 = 16 hari.
    # Harga sewa = Rp 1.500.000
    # Prorata = (16 / 30) * 1.500.000 = Rp 800.000
    start = date(2026, 11, 15)
    amount = prorated_amount(1500000, start)
    assert amount == 800000

    # Masuk tanggal 1 (sebulan penuh) = Rp 1.500.000
    start_full = date(2026, 11, 1)
    assert prorated_amount(1500000, start_full) == 1500000


# ==========================================
# TEST 4: Aturan Bisnis 3 (Denda 2% per minggu, max 10%)
# ==========================================
def test_rule_3_late_fee_calculation():
    # 0 hari (tepat waktu) = 0%
    assert late_fee_percent(0) == 0
    # 1 - 7 hari (minggu 1) = 2%
    assert late_fee_percent(1) == 2
    assert late_fee_percent(7) == 2
    # 8 - 14 hari (minggu 2) = 4%
    assert late_fee_percent(8) == 4
    assert late_fee_percent(14) == 4
    # 15 - 21 hari (minggu 3) = 6%
    assert late_fee_percent(15) == 6
    # 22 - 28 hari (minggu 4) = 8%
    assert late_fee_percent(22) == 8
    # > 28 hari = cap di 10%
    assert late_fee_percent(29) == 10
    assert late_fee_percent(60) == 10

    # Uji rupiah nominal (Rp 1.000.000)
    assert late_fee_amount(1000000, 3) == 20000    # 2%
    assert late_fee_amount(1000000, 10) == 40000   # 4%
    assert late_fee_amount(1000000, 35) == 100000  # Max 10%


# ==========================================
# TEST 5: Aturan Bisnis 4 (Tagihan Tidak Boleh Terbit 2x)
# ==========================================
def test_rule_4_unique_monthly_bill(app, client, basic, seed_data):
    room2 = seed_data["room2"]
    tenant2 = seed_data["tenant2"]

    c = create_contract(room2.id, tenant2.id, date(2026, 11, 1))
    db.session.commit()

    # Terbitkan tagihan pertama
    res1 = client.post("/api/bills", json={"contract_id": c.id, "year": 2026, "month": 11}, headers=basic)
    assert res1.status_code == 201

    # Terbitkan tagihan kedua untuk periode yang sama -> Wajib Conflict (409)
    res2 = client.post("/api/bills", json={"contract_id": c.id, "year": 2026, "month": 11}, headers=basic)
    assert res2.status_code == 409


# ==========================================
# TEST 6: Tantangan K12 - Job Queue & Worker Processing
# ==========================================
def test_k12_worker_processes_billing_queue(app, client, basic, seed_data):
    room1 = seed_data["room1"]
    tenant1 = seed_data["tenant1"]
    c = create_contract(room1.id, tenant1.id, date(2026, 11, 1))
    db.session.commit()

    # 1. API menerima request trigger job (POST /api/jobs/generate-bills)
    res = client.post("/api/jobs/generate-bills", json={"year": 2026, "month": 11}, headers=basic)
    assert res.status_code == 202
    job_id = res.get_json()["id"]

    # 2. Worker meng-claim job
    job = claim_next_job()
    assert job is not None
    assert job.id == job_id
    assert job.status == BillingJob.PROCESSING

    # 3. Worker memproses job sampai selesai
    process_job(job)
    assert job.status == BillingJob.COMPLETED
    assert job.created_count >= 1

    # 4. Verifikasi tagihan benar-benar masuk di database
    bill = Bill.query.filter_by(contract_id=c.id, period_year=2026, period_month=11).first()
    assert bill is not None
    assert bill.status == Bill.UNPAID


# ==========================================
# TEST 7: Akses admin (login, API wajib admin)
# ==========================================
def test_api_requires_admin(client, seed_data):
    assert client.get("/api/rooms").status_code == 401
    assert client.post("/api/bills", json={}).status_code == 401


def test_api_basic_auth_wrong_password(client, admin):
    token = base64.b64encode(f"{ADMIN_EMAIL}:salah".encode()).decode()
    assert client.get("/api/rooms", headers={"Authorization": f"Basic {token}"}).status_code == 401


def test_login_wrong_password_rejected(client, admin):
    res = client.post("/login", data={"email": ADMIN_EMAIL, "password": "salah"})
    assert res.status_code == 401


def test_admin_pages_redirect_to_login(client):
    for path in ("/dashboard", "/admin/bookings", "/admin/users"):
        res = client.get(path)
        assert res.status_code == 302 and "/login" in res.headers["Location"]


def test_admin_create_user_min_password(adminc):
    csrf = csrf_of(adminc, "/admin/users/new")
    adminc.post("/admin/users/new", data={"email": "baru@test.com", "password": "pendek", "csrf_token": csrf})
    assert db.session.scalar(db.select(User.id).filter_by(email="baru@test.com")) is None
    adminc.post("/admin/users/new", data={"email": "Baru@Test.com", "password": "panjang-123", "csrf_token": csrf})
    assert db.session.scalar(db.select(User.id).filter_by(email="baru@test.com")) is not None


def test_admin_cannot_delete_self(adminc, admin):
    csrf = csrf_of(adminc, "/admin/users")
    adminc.post(f"/admin/users/{admin.id}/delete", data={"csrf_token": csrf})
    assert db.session.get(User, admin.id) is not None


# ==========================================
# TEST 8: Portal publik tanpa login
# ==========================================
def test_public_pages_open_without_login(client, seed_data):
    room = seed_data["room1"]
    for path in ("/", f"/kamar/{room.id}", f"/kamar/{room.id}/ajukan", "/status"):
        assert client.get(path).status_code == 200
    assert b"Kos Sejahtera" in client.get("/").data


def book_form(room, **over):
    data = {"name": "Budi Santoso", "email": "Budi@Test.com", "phone": "0812-3456-7890",
            "start_date": "2099-01-01", "notes": "perokok: tidak"}
    data.update(over)
    return data


def test_public_booking_creates_pending(client, seed_data):
    room = seed_data["room1"]
    csrf = csrf_of(client, f"/kamar/{room.id}/ajukan")
    res = client.post(f"/kamar/{room.id}/ajukan", data={**book_form(room), "csrf_token": csrf})
    assert res.status_code == 302
    b = db.session.scalar(db.select(BookingRequest))
    assert b.status == BookingRequest.PENDING
    assert b.email == "budi@test.com" and b.phone == "081234567890"
    assert b.created_at is not None and b.decided_at is None
    assert db.session.scalar(db.select(db.func.count()).select_from(Contract)) == 0


def test_public_booking_requires_csrf(client, seed_data):
    room = seed_data["room1"]
    res = client.post(f"/kamar/{room.id}/ajukan", data=book_form(room))
    assert res.status_code == 400
    assert db.session.scalar(db.select(BookingRequest.id)) is None


def test_booking_validation(client, seed_data):
    room = seed_data["room1"]
    csrf = csrf_of(client, f"/kamar/{room.id}/ajukan")
    for bad in ({"phone": "abc"}, {"email": "bukan-email"}, {"start_date": "2000-01-01"}, {"name": ""}):
        res = client.post(f"/kamar/{room.id}/ajukan", data={**book_form(room, **bad), "csrf_token": csrf})
        assert res.status_code == 422, bad
    assert db.session.scalar(db.select(BookingRequest.id)) is None


def test_booking_occupied_room_and_duplicate_pending(app, seed_data):
    r1, r2, t1 = seed_data["room1"], seed_data["room2"], seed_data["tenant1"]
    create_contract(r1.id, t1.id, date(2026, 11, 1))
    db.session.commit()
    with pytest.raises(ConflictError):
        submit_booking(r1.id, "X", "x@test.com", "081234567890", "2099-01-01")
    submit_booking(r2.id, "X", "x@test.com", "081234567890", "2099-01-01")
    db.session.commit()
    with pytest.raises(ConflictError):
        submit_booking(r2.id, "X", "x@test.com", "081234567890", "2099-02-01")


# ==========================================
# TEST 9: Admin menyetujui / menolak
# ==========================================
def make_booking(room, **over):
    b = submit_booking(room.id, over.get("name", "Budi Santoso"), over.get("email", "budi@test.com"),
                       over.get("phone", "081234567890"), "2099-01-01")
    db.session.commit()
    return b


def test_admin_approve_creates_tenant_and_active_contract(adminc, admin, seed_data):
    b = make_booking(seed_data["room1"])
    csrf = csrf_of(adminc, "/admin/bookings")
    res = adminc.post(f"/admin/bookings/{b.id}/approve", data={"csrf_token": csrf})
    assert res.status_code == 302
    db.session.refresh(b)
    assert b.status == BookingRequest.APPROVED and b.decided_at and b.decided_by == admin.id
    assert db.session.get(Tenant, b.tenant_id).email == "budi@test.com"
    assert db.session.get(Contract, b.contract_id).status == Contract.ACTIVE


def test_approve_reuses_existing_tenant(app, admin, seed_data):
    t1 = seed_data["tenant1"]  # adli@example.com / 081234567890
    b = make_booking(seed_data["room2"], name="Adli", email="adli@example.com", phone="081234567890")
    approve_booking(b.id, admin.id)
    db.session.commit()
    assert b.tenant_id == t1.id
    assert db.session.scalar(db.select(db.func.count()).select_from(Tenant)) == 2


def test_approve_blocked_if_room_taken_meanwhile(app, admin, seed_data):
    room, t2 = seed_data["room1"], seed_data["tenant2"]
    b = make_booking(room)
    create_contract(room.id, t2.id, date(2026, 11, 1))
    db.session.commit()
    with pytest.raises(ConflictError):
        approve_booking(b.id, admin.id)
    db.session.rollback()
    assert db.session.get(BookingRequest, b.id).status == BookingRequest.PENDING


def test_admin_reject_keeps_history_and_allows_new_request(adminc, admin, seed_data):
    room = seed_data["room1"]
    b = make_booking(room)
    csrf = csrf_of(adminc, "/admin/bookings")
    adminc.post(f"/admin/bookings/{b.id}/reject", data={"csrf_token": csrf})
    db.session.refresh(b)
    assert b.status == BookingRequest.REJECTED and b.decided_at and b.contract_id is None
    # ditolak tidak dihapus; pengajuan ulang membuat baris baru
    make_booking(room)
    assert db.session.scalar(db.select(db.func.count()).select_from(BookingRequest)) == 2


def test_decision_is_final_and_needs_csrf(adminc, admin, seed_data):
    b = make_booking(seed_data["room1"])
    assert adminc.post(f"/admin/bookings/{b.id}/approve", data={}).status_code == 400
    db.session.refresh(b)
    assert b.status == BookingRequest.PENDING
    csrf = csrf_of(adminc, "/admin/bookings")
    adminc.post(f"/admin/bookings/{b.id}/reject", data={"csrf_token": csrf})
    adminc.post(f"/admin/bookings/{b.id}/approve", data={"csrf_token": csrf})
    db.session.refresh(b)
    assert b.status == BookingRequest.REJECTED and b.contract_id is None


def test_admin_bookings_page_has_confirm_dialog(adminc, seed_data):
    make_booking(seed_data["room1"])
    html = adminc.get("/admin/bookings").get_data(as_text=True)
    assert "confirm(" in html and 'name="csrf_token"' in html and "Budi Santoso" in html


# ==========================================
# TEST 10: Cek status dengan email + HP
# ==========================================
def test_status_lookup_pending_then_approved_with_bills(client, admin, seed_data):
    b = make_booking(seed_data["room1"])
    csrf = csrf_of(client, "/status")
    ok = {"email": "BUDI@test.com", "phone": "0812-3456-7890", "csrf_token": csrf}
    html = client.post("/status", data=ok).get_data(as_text=True)
    assert "Budi Santoso" in html and "Menunggu" in html

    approve_booking(b.id, admin.id)
    c = db.session.get(Contract, b.contract_id)
    from kosanhub.services.billing import create_bill
    create_bill(c, 2099, 1)
    db.session.commit()
    html = client.post("/status", data=ok).get_data(as_text=True)
    assert "Disetujui" in html and "2099-01" in html and "Tagihan Sewa" in html


def test_status_lookup_needs_both_email_and_phone(client, admin, seed_data):
    make_booking(seed_data["room1"])
    csrf = csrf_of(client, "/status")
    # email benar, HP salah -> tidak membocorkan data
    res = client.post("/status", data={"email": "budi@test.com", "phone": "089999999999", "csrf_token": csrf})
    assert res.status_code == 404 and "Budi Santoso" not in res.get_data(as_text=True)
    # tanpa CSRF ditolak
    assert client.post("/status", data={"email": "budi@test.com", "phone": "081234567890"}).status_code == 400


def test_status_does_not_leak_other_tenants(client, admin, seed_data):
    approve_booking(make_booking(seed_data["room1"]).id, admin.id)
    approve_booking(make_booking(seed_data["room2"], name="Siti", email="siti@test.com", phone="085555555555").id, admin.id)
    db.session.commit()
    csrf = csrf_of(client, "/status")
    html = client.post("/status", data={"email": "siti@test.com", "phone": "085555555555", "csrf_token": csrf}).get_data(as_text=True)
    assert "Siti" in html and "Budi Santoso" not in html


# ==========================================
# UI Fase 3: auto-price kontrak (Gap 3) & halaman bayar 2 kolom (Gap 4)
# ==========================================
def test_contract_form_exposes_room_price(adminc, seed_data):
    html = adminc.get("/admin/contracts/new").get_data(as_text=True)
    assert f'data-price="{seed_data["room1"].monthly_price}"' in html
    assert f'data-price="{seed_data["room2"].monthly_price}"' in html


def test_pay_page_two_column_and_submit(adminc, seed_data):
    c = create_contract(seed_data["room1"].id, seed_data["tenant1"].id, date(2026, 11, 1))
    db.session.commit()
    bill = Bill(contract_id=c.id, period_year=2099, period_month=1, base_amount=1000000,
                total=1000000, due_date=date(2099, 1, 10))
    db.session.add(bill)
    db.session.commit()
    res = adminc.get(f"/admin/bills/{bill.id}/pay")
    html = res.get_data(as_text=True)
    assert res.status_code == 200
    assert "pay-layout" in html and 'data-outstanding="1000000"' in html
    assert 'data-action="fill-outstanding"' in html and "csrf_token" in html
    csrf = csrf_of(adminc, f"/admin/bills/{bill.id}/pay")
    res = adminc.post(f"/admin/bills/{bill.id}/pay", data={
        "amount": "1000000", "paid_on": "2099-01-05", "method": "QRIS", "csrf_token": csrf})
    assert res.status_code == 302
    assert db.session.get(Bill, bill.id).status == Bill.PAID


def test_contracts_page_has_end_button(adminc, seed_data):
    c = create_contract(seed_data["room1"].id, seed_data["tenant1"].id, date(2026, 11, 1))
    html = adminc.get("/contracts").get_data(as_text=True)
    assert 'data-action="end-contract"' in html and f"/admin/contracts/{c.id}/end" in html
