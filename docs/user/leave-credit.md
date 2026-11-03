# Leave Credit from Attendance

Employees earn their leaves by the days they work. Each day, the system credits each leave type in the
employee's Leave Policy in proportion to the worked days.

Example: the Leave Policy gives 20 EL a year, and the year has 300 working days. The employee gets 1 EL for
each 15 worked days. An employee who works 150 days gets 10 EL, not 20.

## Formula

    leaves earned = worked days x annual allocation / working days of the Leave Period

- **Annual allocation**: the value of the leave type in the Leave Policy.
- **Working days**: the days of the Leave Period minus the holidays of the employee's Holiday List (or of
  the company default Holiday List).
- **Worked days**, from the start of the allocation to yesterday:

| Attendance | Worked days |
|---|---|
| Present, Work From Home | 1 |
| Half Day | 0.5. 1 if the other half is a paid leave |
| On Leave, paid leave type | 1 |
| On Leave, Leave Without Pay | 0 |
| Absent, no attendance | 0 |

- The result is rounded down to the **Rounding** of the Leave Type (0.25, 0.5 or 1). It is never more than
  the annual allocation or the **Max Leaves Allowed** of the Leave Type.

The daily job adds only the difference to the leaves already credited. Each credit adds a Leave Ledger
Entry and a comment on the Leave Allocation, for example "Credited 0.5 leave(s) for 156 worked days from
01-04-2026 to 10-10-2026". The **Employee Leave Balance** report and Leave Application use the Leave
Ledger, so they show the credit.

If an attendance is cancelled later, the system does not take back a leave that it credited.

## Setup (HR Manager, once a year)

1. **Leave Type**: for each leave type that is earned by attendance (EL, SL and the others), set
   **Is Earned Leave**, a **Rounding** and the **Applicable After (Working Days)** rule. Do not set it on
   Leave Without Pay.
2. **Leave Period**: make one for the year, for example 01-04-2026 to 31-03-2027, for the company.
3. **Leave Policy**: add a row for each leave type with its **Annual Allocation**. Submit it.
4. **Leave Policy Assignment**: assign the policy to the employees for the Leave Period. Use the
   bulk assignment from the Leave Policy Assignment list. The Leave Allocations start at 0 leaves.

The next daily run credits the attendance since the start of each allocation.

ERPNext's own monthly credit (annual allocation / 12 each month) is stopped, so leaves are credited only
from attendance.
