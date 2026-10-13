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
| Access restricted clinical workflows | Not yet implemented | Not yet implemented | Not yet implemented | Not yet implemented |

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
