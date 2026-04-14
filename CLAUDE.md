# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the development server (port 5001)
python app.py

# Install dependencies
pip install -r requirements.txt

# Run tests
pytest

# Run a single test file
pytest tests/test_routes.py
```

## Architecture

**Spendly** is a Flask-based personal expense tracker. The stack is intentionally minimal: Flask + Jinja2 templates + vanilla CSS/JS + SQLite.

### Request flow

```
Browser → Flask route (app.py) → render_template() → Jinja2 (base.html + child template)
```

All pages extend `templates/base.html`, which provides the navbar, footer, and asset links (`static/css/style.css`, `static/js/main.js`).

### Key files

| File | Purpose |
|------|---------|
| `app.py` | All Flask routes. Currently renders templates only — business logic TBD. |
| `database/db.py` | SQLite helpers: `get_db()`, `init_db()`, `seed_db()` — stub, not yet implemented. |
| `static/css/style.css` | Single stylesheet for the entire site. Uses CSS custom properties (`--ink`, `--accent`, `--font-display`, etc.) defined at the top. |
| `static/js/main.js` | Placeholder — JS is currently inline per-template in `{% block scripts %}`. |

### Routes (current state)

- `GET /` — landing page
- `GET /login` — login form
- `GET /register` — registration form
- `GET /privacy` — privacy policy
- Placeholder routes exist for logout, profile, and expense CRUD (Steps 3–9)

### CSS conventions

All design tokens are CSS custom properties at the top of `style.css`. When adding new styles, use existing variables (`--ink`, `--ink-muted`, `--ink-soft`, `--accent`, `--border`, `--radius-sm/md/lg`, `--font-display`, `--font-body`) rather than hardcoding values.

The stylesheet is organized in layout order: reset → nav → hero → features → CTA → auth → buttons → footer → mock browser component. New page-specific styles go at the bottom, or inline in `{% block head %}` for page-scoped rules.

### Template conventions

- Page-scoped CSS goes in `{% block head %}` (inline `<style>` tag)
- Page-scoped JS goes in `{% block scripts %}` (inline `<script>` tag)
- `main.js` is loaded globally but is currently empty — prefer inline scripts per template until a clear need for shared JS emerges
