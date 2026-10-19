# Role Permission Matrix

This matrix records the approved staff roles that are enforced in the current project architecture. It is intentionally aligned to the existing `StaffProfile` design and does not invent extra roles or unnecessary permissions.

## Approved roles

| Role | Internal value | Description |
| --- | --- | --- |
| Administrator | `administrator` | Full staff account administration and security-sensitive account controls |
| Receptionist | `receptionist` | Operational support access limited to authorized account and support functions |
| Doctor/Clinician | `clinician` | Clinical access limited to approved clinical functions |
| Nurse | `nurse` | Care-related access limited to approved care or support functions |

## Staff-management permissions

This milestone implements the authentication and account-management authorization layer for the approved Smart Clinic requirements. The same approved role model is enforced consistently across the staff and patient modules.

| Capability | Administrator | Receptionist | Doctor/Clinician | Nurse |
| --- | --- | --- | --- | --- |
| Search/view staff directory and profiles | Yes | No | No | No |
| Register staff account | Yes | No | No | No |
| Edit staff account details | Yes | No | No | No |
| Assign approved role | Yes | No | No | No |
| Activate/deactivate staff access | Yes | No | No | No |
| Change own password | Yes | Yes | Yes | Yes |
| Access staff home | Yes | Yes | Yes | Yes |
| Access restricted clinical workflows | No routine clinical-note access | No | Assigned-care access only | Not implemented |

## Appointment permissions (M07)

Appointment permissions implement the approved responsibility boundaries:
Receptionists manage appointment logistics, while clinicians can access only
appointments assigned to them. Administrator access is limited to scheduling
administration and does not grant clinical-record access.

| Capability | Administrator | Receptionist | Doctor/Clinician | Nurse |
| --- | --- | --- | --- | --- |
| List/search appointments | Yes | Yes | Assigned appointments only | No |
| View appointment details | Yes | Yes | Assigned appointments only | No |
| Create appointments | Yes | Yes | No | No |
| Edit/reschedule Scheduled or Confirmed appointments | Yes | Yes | No | No |
| Cancel Scheduled or Confirmed appointments | Yes | Yes | No | No |
| Change attendance, completion, or missed status | No | No | No | No |

All appointment writes are server-authorized and protected by CSRF. Clinician
record scope is enforced by filtering the queryset, so another clinician's
appointment returns 404 even when its numeric URL is guessed. The appointment
role policy was selected for M07 because M01 describes receptionist scheduling
logistics and assigned-care clinician scope but does not enumerate appointment
routes in the original matrix. Nurses are denied appointment routes in this
milestone.

## Consultation and medical-history permissions (M09)

Consultation and patient-history routes are restricted server-side to active
Doctor/Clinician profiles. Access is limited to a patient linked to a
non-cancelled appointment assigned to that clinician, or to a patient for whom
the clinician already authored a consultation or separate history entry.
History displays the patient's consultation and longitudinal-entry records
once that care relationship is established. A consultation can only select an
appointment for the same patient and clinician. Only the original clinician
can amend a consultation; the prior version is retained and visible within
assigned-care scope.

Administrators do not receive clinical-note access by virtue of their
administrative role, and Receptionists do not receive clinical-history access.
Nurses have no consultation/history route in this implementation: the project
does not yet define an assignment link for nurses or a specific nursing
documentation workflow. This is a conservative boundary, not a grant of
unrestricted clinical access.

## Authorization rules

- Role checks must be evaluated server-side.
- Authenticated staff without the required role receive a 403 response.
- Inactive users and inactive staff profiles are denied access.
- Staff accounts are deactivated rather than deleted; profile and Django-user
  active states are changed together by a POST-only action.
- An administrator cannot deactivate their own account. The last active
  administrator cannot be demoted.
- The role field remains the approved source of truth; no conflicting role definitions are introduced.

## Patient permissions in the approved scope

The approved M01 requirements define the four approved staff roles and the patient-management boundaries implemented in the current project. The current patient demographic scope is:

| Capability | Administrator | Receptionist | Doctor/Clinician | Nurse |
| --- | --- | --- | --- | --- |
| List/search demographic records | Yes | Yes | No | No |
| View demographic patient profile | Yes | Yes | No | No |
| Register patient | Yes | Yes | No | No |
| Edit patient demographics | Yes | Yes | No | No |
| Archive or restore patient | Yes | No | No | No |
| View clinical notes/history through M05 pages | No | No | No | No |

Archive and restore are soft state changes, require POST and CSRF protection, and are restricted to administrators. No patient delete operation is offered. The M05 list and profile do not expose clinical notes or history. These permissions are enforced server-side and remain aligned with the approved role model.
