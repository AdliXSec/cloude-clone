/* KosanHub — Vanilla JS Interactivity (ES6) */

(function() {
  'use strict';

  /* ===== CSRF + Form Helpers ===== */
  function getCsrfToken() {
    const inp = document.querySelector('input[name="csrf_token"]');
    return inp ? inp.value : '';
  }

  /* ===== Toast / Flash Messages ===== */
  function initFlashDismiss() {
    const container = document.querySelector('.toasts');
    if (!container) return;

    document.querySelectorAll('.toast').forEach(toast => {
      const closeBtn = toast.querySelector('.toast-close');
      if (closeBtn) {
        closeBtn.addEventListener('click', () => {
          toast.classList.add('leaving');
          setTimeout(() => toast.remove(), 250);
        });
      }

      // Auto-dismiss ok class setelah 5 detik
      if (toast.classList.contains('toast-ok')) {
        setTimeout(() => {
          if (document.contains(toast)) {
            toast.classList.add('leaving');
            setTimeout(() => toast.remove(), 250);
          }
        }, 5000);
      }
    });
  }

  /* ===== Modal Konfirmasi ===== */
  function escapeHtml(text) {
    const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
    return String(text == null ? '' : text).replace(/[&<>"']/g, m => map[m]);
  }

  function showConfirmModal(message, onConfirm) {
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.innerHTML = `
      <div class="modal-box">
        <h2>Konfirmasi</h2>
        <p>${message}</p>
        <div class="modal-actions">
          <button class="btn-ghost" data-action="cancel">Batal</button>
          <button class="btn" data-action="confirm">Lanjutkan</button>
        </div>
      </div>
    `;

    const close = () => {
      modal.remove();
      document.body.classList.remove('modal-open');
    };
    modal.querySelector('[data-action="cancel"]').addEventListener('click', close);
    modal.querySelector('[data-action="confirm"]').addEventListener('click', () => {
      close();
      if (onConfirm) onConfirm();
    });

    document.body.appendChild(modal);
    document.body.classList.add('modal-open');
    modal.addEventListener('click', (e) => {
      if (e.target === modal) close();
    });
  }

  function initConfirmModal() {
    document.querySelectorAll('[data-confirm]').forEach(elem => {
      const originalSubmit = elem.onsubmit;
      elem.onsubmit = function(e) {
        e.preventDefault();
        const msg = elem.getAttribute('data-confirm');
        const form = elem;
        showConfirmModal(escapeHtml(msg), () => {
          if (originalSubmit) {
            originalSubmit.call(form, { type: 'submit' });
          } else {
            form.submit();
          }
        });
      };
    });

    // Tombol delete dengan confirm
    document.querySelectorAll('[data-delete-confirm]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        const msg = btn.getAttribute('data-delete-confirm');
        const form = btn.closest('form');
        showConfirmModal(escapeHtml(msg), () => {
          if (form) form.submit();
        });
      });
    });
  }

  /* ===== Navbar Dropdown ===== */
  function initNavDropdowns() {
    const navToggle = document.querySelector('.nav-toggle');
    const topbar = document.querySelector('.topbar');
    if (navToggle && topbar) {
      navToggle.addEventListener('click', () => {
        topbar.classList.toggle('open');
      });
    }

    document.querySelectorAll('.nav-dd').forEach(dd => {
      const btn = dd.querySelector('button');
      if (btn) {
        btn.addEventListener('click', (e) => {
          e.preventDefault();
          document.querySelectorAll('.nav-dd').forEach(other => {
            if (other !== dd) other.classList.remove('open');
          });
          dd.classList.toggle('open');
        });
      }
    });

    // Tutup dropdown saat klik di luar
    document.addEventListener('click', (e) => {
      if (!e.target.closest('.nav-dd') && !e.target.closest('.nav-toggle')) {
        document.querySelectorAll('.nav-dd').forEach(dd => dd.classList.remove('open'));
      }
    });
  }

  /* ===== Client-side Filter (Pill + Category) ===== */
  function initClientFilter() {
    const catStrip = document.querySelector('.cat-strip');
    const cards = document.querySelectorAll('.card');
    const rows = document.querySelectorAll('tbody tr');

    if (catStrip || cards.length || rows.length) {
      const doFilter = () => {
        const searchInput = document.querySelector('[data-filter="search"]');
        const statusInput = document.querySelector('[data-filter="status"]');
        const activeCat = document.querySelector('.cat-item.active');

        const searchTerm = searchInput ? searchInput.value.toLowerCase() : '';
        const statusTerm = statusInput ? statusInput.value.toLowerCase() : '';
        const catTerm = activeCat ? activeCat.textContent.toLowerCase() : '';

        (cards.length ? cards : rows).forEach(item => {
          const text = item.textContent.toLowerCase();
          const matchSearch = !searchTerm || text.includes(searchTerm);
          const matchStatus = !statusTerm || text.includes(statusTerm);
          const matchCat = !catTerm || text.includes(catTerm);
          item.style.display = matchSearch && matchStatus && matchCat ? '' : 'none';
        });
      };

      document.querySelectorAll('[data-filter]').forEach(inp => {
        inp.addEventListener('input', doFilter);
        inp.addEventListener('change', doFilter);
      });

      document.querySelectorAll('.cat-item').forEach(item => {
        item.addEventListener('click', (e) => {
          e.preventDefault();
          document.querySelectorAll('.cat-item').forEach(c => c.classList.remove('active'));
          item.classList.add('active');
          doFilter();
        });
      });

      doFilter();
    }
  }

  /* ===== View Toggle (Grid vs Table) ===== */
  function initViewToggle() {
    const toggleBtns = document.querySelectorAll('.seg button');
    const gridContainer = document.querySelector('.card-grid');
    const tableWrap = document.querySelector('.table-wrap');

    if (!toggleBtns.length) return;

    const viewKey = document.body.id.replace('_', '-') + '_view';
    const saved = localStorage.getItem(viewKey) || 'grid';

    toggleBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        const view = btn.dataset.view;
        toggleBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        if (gridContainer) {
          gridContainer.style.display = view === 'grid' ? 'grid' : 'none';
        }
        if (tableWrap) {
          tableWrap.style.display = view === 'table' ? 'block' : 'none';
        }

        localStorage.setItem(viewKey, view);
      });

      if (btn.dataset.view === saved) {
        btn.classList.add('active');
        if (gridContainer && saved === 'table') {
          gridContainer.style.display = 'none';
        }
        if (tableWrap && saved === 'grid') {
          tableWrap.style.display = 'none';
        }
      }
    });
  }

  /* ===== Auto-fill Harga Kamar ===== */
  function initContractPriceAutofill() {
    const roomSelect = document.querySelector('[name="room_id"]');
    const priceInput = document.querySelector('[name="monthly_price"]');

    if (roomSelect && priceInput) {
      roomSelect.addEventListener('change', (e) => {
        const opt = e.target.options[e.target.selectedIndex];
        const price = opt.dataset.price;
        if (price) {
          priceInput.value = price;
        }
      });
    }
  }

  /* ===== Payment Helper ===== */
  function initPaymentHelper() {
    const amountInput = document.querySelector('[name="amount"]');
    const fillBtn = document.querySelector('[data-action="fill-outstanding"]');
    const outstandingVal = document.querySelector('[data-outstanding]');
    const hint = document.querySelector('[data-hint="payment"]');

    if (!amountInput || !outstandingVal || !hint) return;

    const outstanding = parseFloat(outstandingVal.dataset.outstanding) || 0;

    if (fillBtn) {
      fillBtn.addEventListener('click', (e) => {
        e.preventDefault();
        amountInput.value = outstanding.toFixed(0);
        updatePaymentHint();
      });
    }

    const updatePaymentHint = () => {
      const amount = parseFloat(amountInput.value) || 0;
      if (amount <= 0) {
        hint.textContent = '';
        hint.className = 'hint';
      } else if (amount < outstanding) {
        hint.textContent = `✓ Pembayaran Parsial (Sisa: Rp ${(outstanding - amount).toLocaleString('id-ID')})`;
        hint.className = 'hint warn';
      } else if (amount >= outstanding) {
        const overpay = amount - outstanding;
        hint.textContent = overpay > 0
          ? `✓ Pembayaran Lunas (Lebih bayar: Rp ${overpay.toLocaleString('id-ID')})`
          : `✓ Pembayaran Lunas`;
        hint.className = 'hint ok';
      }
    };

    amountInput.addEventListener('input', updatePaymentHint);
    updatePaymentHint();
  }

  /* ===== Job Polling ===== */
  function initJobPolling() {
    const jobRows = document.querySelectorAll('tr[data-job-id]');
    if (!jobRows.length) return;

    const pollJob = (jobId) => {
      const row = document.querySelector(`tr[data-job-id="${jobId}"]`);
      if (!row) return;

      fetch(`/api/jobs/${jobId}`)
        .then(r => r.json())
        .then(data => {
          const statusCell = row.querySelector('[data-job-status]');
          const createdCell = row.querySelector('[data-job-created]');
          const skippedCell = row.querySelector('[data-job-skipped]');
          const errorCell = row.querySelector('[data-job-error]');

          if (statusCell) {
            const oldStatus = statusCell.dataset.jobStatus;
            statusCell.dataset.jobStatus = data.status;
            statusCell.innerHTML = `<span class="badge badge-${data.status.toLowerCase()}">${data.status}</span>`;

            // Henti polling jika selesai
            if ((data.status === 'DONE' || data.status === 'ERROR') && oldStatus !== data.status) {
              return;
            }
          }

          if (createdCell) createdCell.textContent = data.created_count || 0;
          if (skippedCell) skippedCell.textContent = data.skipped_count || 0;
          if (errorCell && data.error) errorCell.textContent = data.error;

          // Polling ulang setiap 3 detik jika masih PENDING/PROCESSING
          if (data.status === 'PENDING' || data.status === 'PROCESSING') {
            setTimeout(() => pollJob(jobId), 3000);
          }
        })
        .catch(err => console.error('Poll error:', err));
    };

    jobRows.forEach(row => {
      const jobId = row.dataset.jobId;
      const status = row.dataset.jobStatus || '';
      if (status === 'PENDING' || status === 'PROCESSING') {
        pollJob(jobId);
      }
    });
  }

  /* ===== Password Toggle ===== */
  function initPasswordToggle() {
    document.querySelectorAll('.pw').forEach(container => {
      const input = container.querySelector('input[type="password"]');
      const btn = container.querySelector('.pw-btn');

      if (input && btn) {
        btn.addEventListener('click', (e) => {
          e.preventDefault();
          const isPassword = input.type === 'password';
          input.type = isPassword ? 'text' : 'password';
          btn.textContent = isPassword ? '👁' : '👁‍🗨';
        });
      }
    });

    // Validasi konfirmasi password
    const newPw = document.querySelector('[name="new_password"]');
    const confirmPw = document.querySelector('[name="confirm_password"]');
    const hint = document.querySelector('[data-hint="password-match"]');

    if (newPw && confirmPw && hint) {
      const checkMatch = () => {
        if (!confirmPw.value) {
          hint.textContent = '';
          hint.className = 'hint';
        } else if (newPw.value === confirmPw.value) {
          hint.textContent = '✓ Password cocok';
          hint.className = 'hint ok';
        } else {
          hint.textContent = '✗ Password tidak cocok';
          hint.className = 'hint bad';
        }
      };

      newPw.addEventListener('input', checkMatch);
      confirmPw.addEventListener('input', checkMatch);
    }

    // Password strength meter
    const pwInput = document.querySelector('[name="password"], [name="new_password"]');
    const meter = document.querySelector('.meter > i');
    if (pwInput && meter) {
      pwInput.addEventListener('input', () => {
        const len = pwInput.value.length;
        const strength = Math.min(100, len * 12);
        const color = strength < 40 ? '#B42318' : strength < 70 ? '#B54708' : '#027A48';
        meter.style.width = strength + '%';
        meter.style.background = color;
      });
    }
  }

  /* ===== Rupiah Formatter ===== */
  window.formatRupiah = function(num) {
    return new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR', minimumFractionDigits: 0 }).format(num);
  };

  /* ===== Modal Tagihan (Generate) ===== */
  function initBillingModal() {
    const btn = document.querySelector('[data-action="open-generate-billing"]');
    if (!btn) return;

    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const modal = document.createElement('div');
      modal.className = 'modal';
      const today = new Date();
      const year = today.getFullYear();
      const month = String(today.getMonth() + 1).padStart(2, '0');

      modal.innerHTML = `
        <div class="modal-box">
          <h2>Generate Tagihan</h2>
          <form action="/admin/jobs/generate" method="POST">
            <input type="hidden" name="csrf_token" value="${getCsrfToken()}">
            <div class="field">
              <span>Bulan</span>
              <input type="number" name="month" min="1" max="12" value="${month}" required>
            </div>
            <div class="field">
              <span>Tahun</span>
              <input type="number" name="year" min="2020" value="${year}" required>
            </div>
            <div class="modal-actions">
              <button type="button" class="btn-ghost" data-action="cancel">Batal</button>
              <button type="submit" class="btn">Generate</button>
            </div>
          </form>
        </div>
      `;

      document.body.appendChild(modal);
      document.body.classList.add('modal-open');

      modal.querySelector('[data-action="cancel"]').addEventListener('click', () => {
        modal.remove();
        document.body.classList.remove('modal-open');
      });

      modal.addEventListener('click', (e) => {
        if (e.target === modal) modal.remove();
      });
    });
  }

  /* ===== Modal Akhiri Kontrak ===== */
  function initEndContractModal() {
    document.querySelectorAll('[data-action="end-contract"]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        const contractId = btn.dataset.contractId;
        const contractDesc = btn.dataset.contractDesc || '';
        const form = btn.closest('form');

        showConfirmModal(
          `Akhiri kontrak: <strong>${escapeHtml(contractDesc)}</strong>?<br><small style="color: #717171">Aksi ini tidak bisa dibatalkan.</small>`,
          () => {
            if (form) form.submit();
          }
        );
      });
    });
  }

  /* ===== Pill Search Interaktif ===== */
  function initPillSearch() {
    const searchBar = document.querySelector('.pill-search:not(.inline)');
    if (!searchBar) return;

    // Minimal filtering on client side, backend menangani real filtering
    searchBar.addEventListener('submit', (e) => {
      if (e.target.tagName === 'FORM') {
        // Biarkan form submit normal
      }
    });
  }

  /* ===== Init All ===== */
  function init() {
    // Tunggu DOM ready
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', init);
      return;
    }

    initFlashDismiss();
    initConfirmModal();
    initNavDropdowns();
    initClientFilter();
    initViewToggle();
    initContractPriceAutofill();
    initPaymentHelper();
    initJobPolling();
    initPasswordToggle();
    initBillingModal();
    initEndContractModal();
    initPillSearch();
  }

  init();
})();
