# Spec: Delete Expense

## Overview
Allows a logged-in user to permanently remove one of their own expenses from the database. A Delete button appears alongside the existing Edit button in the profile page transaction table. Clicking it submits a POST form to the delete route, which verifies ownership, executes the deletion, and redirects back to the profile with a flash confirmation.

## Depends on
- Step 01 — Database setup (expenses table)
- Step 04/05 — Profile page and its backend routes (transaction table that hosts the button)
- Step 08 — Edit expense (establishes the pattern for ownership-checked expense mutations)

## Routes
- `POST /expenses/<int:id>/delete` — delete the expense owned by the current user — logged-in only

The existing stub in `app.py` (`GET /expenses/<int:id>/delete`) must be changed to accept `POST` only.

## Database changes
No database changes. The `expenses` table already exists with the required schema.

## Templates
- **Modify:** `templates/profile.html` — add a delete `<form>` with a submit button in the `actions` column of the transaction table, beside the existing Edit link. No new template needed; no confirmation modal required.

## Files to change
- `app.py` — replace the stub `delete_expense` route with a working POST implementation
- `database/queries.py` — add `delete_expense(expense_id, user_id)` helper
- `templates/profile.html` — add delete form/button to the actions cell in the transaction table

## Files to create
None.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only (`DELETE FROM expenses WHERE id = ? AND user_id = ?`)
- The route must be `POST`; reject non-POST access (or simply only register the POST method)
- Verify ownership inside `delete_expense` by filtering on both `id` AND `user_id` — never delete by `id` alone
- Redirect to `url_for('profile')` after a successful delete with `flash("Expense deleted.")`
- If the expense does not exist or belongs to another user, `abort(404)`
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Passwords hashed with werkzeug (not applicable here, but retained for completeness)
- The delete button should be visually distinct (e.g. a muted red/danger colour) using existing CSS variables or a minimal new class — no modal required

## Definition of done
- [ ] Visiting `POST /expenses/<int:id>/delete` with a valid, owned expense ID deletes the row and redirects to `/profile` with the flash message "Expense deleted."
- [ ] The deleted expense no longer appears in the transaction table on the profile page
- [ ] Attempting to delete an expense belonging to another user returns 404
- [ ] Attempting to delete a non-existent expense returns 404
- [ ] A logged-out user attempting to POST to the delete route is redirected to `/login`
- [ ] The Delete button is visible next to the Edit link in the transaction table on the profile page
- [ ] Summary stats (total spent, transaction count) update correctly after deletion 
