# Coloring Kiosk — Task Breakdown

Source: `coloring-kiosk-spec.md` + approved plan at
`/home/theron/.claude/plans/use-coloring-kiosk-spec-md-as-instructio-breezy-key.md`.
Already approved by the user via plan-mode. Executing in autonomous build mode.

- [x] 0. Repo scaffolding: directories, `.gitignore`, `requirements.txt`,
      `requirements-dev.txt`, `pytest.ini`, `app/config.py`. No behavior yet.
- [x] 1. Data models: `app/models.py` (Category, Page, PrintLog) + `app/db.py`
      (`init_db`, `get_db`). Test: create tables in-memory, insert/query rows.
- [x] 2. Admin auth: `SessionMiddleware` wiring in `app/main.py`, `require_admin`
      dependency in `app/deps.py`, login/logout routes + `admin/login.html`.
      Test: unauthenticated redirect, wrong/correct password, session
      persistence, logout.
- [ ] 3. Category management: admin routes (create/edit/delete/reorder) +
      `admin/dashboard.html`, `admin/category_form.html`,
      `admin/_category_list.html`. Test: create/edit/reorder, delete blocked
      when pages exist / allowed when empty.
- [ ] 4. Image service + page management: `app/services/images.py`
      (validate/save/thumbnail), admin bulk-upload/delete/recategorize routes
      + `admin/category_detail.html`. Test: bulk upload valid+invalid mix,
      delete, recategorize.
- [ ] 5. Kid UI browsing: `app/routers/kiosk.py` (home/category/preview) +
      `kiosk/home.html`, `kiosk/category.html`, `kiosk/preview.html`,
      `base_kiosk.html`, vendored `htmx.min.js`, `kiosk.css`/`admin.css`.
      Test: home lists categories in order, category lists only its pages,
      preview renders expected page, back-navigation paths exist.
- [ ] 6. Printing service: `app/services/printing.py`
      (`PrinterClient`/`IPPPrinterClient`, `PrinterUnreachableError`,
      `PrinterJobError`, `image_to_pdf`). Test: mocked success,
      unreachable/job-error paths raise correctly, `image_to_pdf` produces
      valid PDF bytes.
- [ ] 7. Rate limiting: `print_log`-backed count of all attempts in trailing
      1h window. Test: limit enforced across mixed statuses, old rows don't
      count, resets after window.
- [ ] 8. Print route wiring: `POST /print/{page_id}` in kiosk router,
      `_print_success.html`/`_print_error.html` fragments with `load
      delay:3s` auto-return. Test: success fragment + log row; printer
      failure and rate-limit each render friendly fragment with no
      exception text leaked; rate-limited requests never call the printer
      client.
- [ ] 9. Docker packaging: `Dockerfile`, `docker-compose.yml`,
      `.env.example`, `.dockerignore`. Verify: image builds, container
      starts, `data/` volume populated on first run.
- [ ] 10. Full verification pass: run entire pytest suite, exercise manual
      admin + kid flows via TestClient/manual server run, confirm
      printer-unreachable and rate-limit paths per plan §Verification.

Dependencies are linear (each task builds on the previous); execute in
order.
