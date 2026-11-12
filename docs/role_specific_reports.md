# Role-specific operational reports

The authenticated `/reports/operations/` page uses server-side role checks and
optional inclusive appointment-date filters. It displays aggregate counts and
does not include patient names, contact details, or clinical note contents.

- **Administrator:** clinic-wide appointment and queue counts plus active
  staff-account count. The existing administrator appointment status report
  remains available separately.
- **Receptionist:** clinic-wide appointment status and current queue counts.
- **Clinician:** assigned appointments and queue counts, plus the clinician's
  own consultation count for the selected date range.
- **Nurse:** clinic appointment/queue counts and that Nurse's recorded
  observation count for the selected date range.

These are operational summaries, not clinical outcome analytics or performance
rankings. They do not calculate wait-time averages or infer care quality.
