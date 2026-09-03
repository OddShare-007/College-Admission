# College Admission Management System

A terminal-based college admission management system written in Python. The project demonstrates common data structures and algorithms while managing student applications, eligibility, merit lists, seat allocation, waitlists, and reports.

## Features

- Admin registration and login with salted password hashes
- Add and validate student applications
- Detect duplicate applications using name and phone number
- Mark students as eligible when they meet the minimum marks requirement
- Generate filtered merit lists
- Search students by ID or department
- Allocate category-wise seats according to quotas
- Move students from waitlists when seats become available
- Generate admission statistics and reports
- Persist application data in JSON format

## Requirements

- Python 3.8 or later
- No third-party packages are required

## Run the application

From this folder, run:

```powershell
python college_admission_system.py
```

On the first run, if `admin_auth.json` does not exist, the application asks you to create an admin account. Otherwise, enter the credentials for the existing account. The application allows three failed login attempts.

## Recommended workflow

1. Add applications using menu option `1`.
2. Check each student's eligibility using option `2`.
3. Generate the merit list with option `4`.
4. Allocate seats with option `7`.
5. Process available waitlist seats with option `8` when required.
6. Review totals using option `9`.
7. Use option `10` to save manually, or option `0` to save and exit.

Only students whose eligibility has been checked and whose marks meet the minimum requirement are included in merit lists and seat allocation.

## Admission rules

| Rule | Value |
| --- | --- |
| Minimum eligibility marks | 33.0 |
| Valid categories | General, OBC, SC, ST, EWS |
| General quota | 40 |
| OBC quota | 27 |
| SC quota | 15 |
| ST quota | 8 |
| EWS quota | 10 |

Applications are validated for non-empty names and departments, marks from 0 to 100, an email containing `@` and `.`, and phone numbers containing at least 10 digits.

## Algorithms and data structures

| Operation | Implementation | Typical complexity |
| --- | --- | --- |
| Merit list | Manual merge sort | `O(n log n)` |
| Student lookup | Binary search over sorted IDs | `O(log n)` |
| Duplicate detection | Set | `O(1)` average |
| Department lookup | Dictionary index | `O(1)` average lookup, excluding result traversal |
| Seat allocation | Category-wise max-heap | `O(n log n)` overall |
| Waitlist processing | `deque` queue | `O(1)` per student moved |

## Data files

- `college_admission_system.py`: application source code
- `admin_auth.json`: local admin username, salt, and password hash
- `admission_data.json`: generated application, allocation, and waitlist data

`admission_data.json` is created when data is saved. Both JSON files contain local application or authentication data and should be protected from unauthorized access. Do not use this application with real applicant information without adding stronger security, access controls, backups, and privacy protections. The current password hashing approach is suitable for a classroom demonstration but should be replaced with a password-specific algorithm such as Argon2 or bcrypt in a production system.

## Project analysis

The system keeps primary student records in a dictionary and maintains additional in-memory indexes for fast searches. These indexes are rebuilt whenever saved data is loaded. Seat allocation is performed independently for each category, with eligible applicants ranked by marks; students exceeding a category quota are placed in that category's waitlist.

This is an educational, single-user, terminal application. It does not provide a web interface, database transactions, concurrent-user support, automated tests, or role-based access control.

## License

No license has been specified for this project.