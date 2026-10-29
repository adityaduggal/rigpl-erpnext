# rigpl_erpnext
Frappe/ERPNext v13 app, Python 3.8. Needs rohit_common.
Before code work read .claude/skills/rigpl-v13/SKILL.md.
Topic notes: docs/ai/<topic>.md. Read only the one the task needs.
Never run bench migrate, backup or run-tests. The user runs them.
Each run-tests command for the user has --skip-before-tests. Without it, the ERPNext hook deletes all Item Price rows on dev-rigpl-v12.
Never commit without asking. Show the changes and wait until the user says yes.
