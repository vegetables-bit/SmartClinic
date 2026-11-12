# Clinic queue management

The clinic queue tracks the visit-day flow for an existing appointment. It
does not replace the appointment schedule or clinical record:

1. Administrator, Receptionist, or Nurse checks in a scheduled/confirmed
   appointment for the configured current date (UTC in the current project
   default). The appointment becomes `attended` and a unique queue entry is
   created as `waiting`.
2. Administrator, Receptionist, or Nurse calls a waiting patient.
3. The assigned Clinician can start a waiting/called queue entry and complete
   an in-progress visit. An Administrator can perform those transitions for
   operational recovery.
4. Completing the queue entry also marks the appointment `completed`.

Every transition is POST-only, checked on the server, recorded with the
authenticated staff actor, and written to the audit log without patient names
or clinical text. Clinicians only see and update their assigned appointments.
Nurses see patient identifiers rather than names on the queue board. The board
contains today's appointments; historical queue entries remain available for
aggregate reporting but there is no historical queue browser yet.

The queue is available at `/queue/`. These role assignments are the
implementation scope for the owner-requested extension. Confirm them with the
project supervisor against the approved M01 baseline before presenting them as
institution-approved policy. The additive migration
`0007_queue_and_reminder_delivery` must be applied before using it:

```powershell
python .\src\manage.py migrate
```

No automatic no-show detection or queue-position prediction is implemented.
