"""
College Admission Management System
Design and Analysis of Algorithms (DAA) Project
Pure backend, terminal-based, no GUI/web interface.

Algorithms/Data Structures used (as per synopsis):
- Merge Sort            -> generate_merit_list()          O(n log n)
- Binary Search          -> search_student() by ID          O(log n)
- Set                    -> check_duplicate()                O(1) avg
- Dictionary / Hashing   -> search_by_department()           O(1) avg lookup
- Heap (Priority Queue)  -> allocate_seats() (category-wise)  O(log n) per op
- Queue (deque)          -> process_waitlist()                O(1) per op
- JSON file              -> save_data() / load_data()         persistence
"""

import json
import os
import hashlib
import secrets
import heapq
from collections import deque, defaultdict
from datetime import datetime

DATA_FILE = "admission_data.json"
AUTH_FILE = "admin_auth.json"

VALID_CATEGORIES = ["General", "OBC", "SC", "ST", "EWS"]
SEAT_QUOTA = {"General": 40, "OBC": 27, "SC": 15, "ST": 8, "EWS": 10}
MIN_ELIGIBILITY_MARKS = 33.0


# --------------------------------------------------------------------------
# CUSTOM EXCEPTIONS
# --------------------------------------------------------------------------
class DuplicateApplicationError(Exception):
    pass


class StudentNotFoundError(Exception):
    pass


class InvalidCategoryError(Exception):
    pass


class ValidationError(Exception):
    pass


class AuthenticationError(Exception):
    pass


# --------------------------------------------------------------------------
# AUTHENTICATION MODULE
# --------------------------------------------------------------------------
class AuthManager:
    """Handles admin account creation and login. Credentials are salted +
    hashed (SHA-256) and stored locally — never stored in plain text."""

    def __init__(self, auth_file=AUTH_FILE):
        self.auth_file = auth_file
        self.max_attempts = 3

    def _hash_password(self, password, salt):
        return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()

    def admin_exists(self):
        return os.path.exists(self.auth_file)

    def register_admin(self, username, password):
        if not username or not password:
            raise ValidationError("Username and password cannot be empty.")
        if len(password) < 4:
            raise ValidationError("Password must be at least 4 characters.")

        salt = secrets.token_hex(8)
        record = {
            "username": username.strip(),
            "salt": salt,
            "password_hash": self._hash_password(password, salt),
        }
        try:
            with open(self.auth_file, "w") as f:
                json.dump(record, f, indent=2)
        except IOError as e:
            raise IOError(f"Could not save admin credentials: {e}")

    def login(self, username, password):
        if not self.admin_exists():
            raise AuthenticationError("No admin account exists. Please register first.")

        try:
            with open(self.auth_file, "r") as f:
                record = json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            raise AuthenticationError(f"Could not read admin credentials: {e}")

        expected_hash = self._hash_password(password, record.get("salt", ""))
        if username.strip() == record.get("username") and expected_hash == record.get("password_hash"):
            return True
        raise AuthenticationError("Invalid username or password.")


# --------------------------------------------------------------------------
# CORE ADMISSION SYSTEM
# --------------------------------------------------------------------------
class AdmissionSystem:
    def __init__(self, data_file=DATA_FILE):
        self.data_file = data_file
        self.students = {}              # id -> student record (dict)
        self.sorted_ids = []            # kept sorted, for binary search
        self.next_id = 1
        self.duplicate_set = set()      # (name_lower, phone) tuples
        self.department_index = defaultdict(list)   # dept -> [ids]  (hashing)
        self.seat_quota = dict(SEAT_QUOTA)
        self.seats_filled = defaultdict(int)
        self.waitlist_queues = defaultdict(deque)    # category -> deque of ids

        self.load_data()

    # ---------------------- INTERNAL HELPERS ----------------------
    def _rebuild_indexes(self):
        """Rebuild in-memory indexes after loading data from disk."""
        self.sorted_ids = sorted(self.students.keys())
        self.duplicate_set.clear()
        self.department_index.clear()
        for sid, rec in self.students.items():
            self.duplicate_set.add((rec["name"].strip().lower(), rec["phone"]))
            self.department_index[rec["department"]].append(sid)

    def _binary_search(self, target_id):
        """Manual binary search over sorted_ids. Returns True/False."""
        lo, hi = 0, len(self.sorted_ids) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            if self.sorted_ids[mid] == target_id:
                return True
            elif self.sorted_ids[mid] < target_id:
                lo = mid + 1
            else:
                hi = mid - 1
        return False

    def _insert_sorted_id(self, new_id):
        """Insert into sorted_ids maintaining sort order (manual insertion)."""
        lo, hi = 0, len(self.sorted_ids)
        while lo < hi:
            mid = (lo + hi) // 2
            if self.sorted_ids[mid] < new_id:
                lo = mid + 1
            else:
                hi = mid
        self.sorted_ids.insert(lo, new_id)

    def _merge_sort(self, arr, key):
        """Manual merge sort, descending by key(item). O(n log n)."""
        if len(arr) <= 1:
            return arr
        mid = len(arr) // 2
        left = self._merge_sort(arr[:mid], key)
        right = self._merge_sort(arr[mid:], key)
        return self._merge(left, right, key)

    def _merge(self, left, right, key):
        result = []
        i = j = 0
        while i < len(left) and j < len(right):
            if key(left[i]) >= key(right[j]):
                result.append(left[i]); i += 1
            else:
                result.append(right[j]); j += 1
        result.extend(left[i:])
        result.extend(right[j:])
        return result

    # ---------------------- MODULE 1: add_application ----------------------
    def add_application(self, name, marks, category, department, email, phone):
        name = (name or "").strip()
        department = (department or "").strip()
        email = (email or "").strip()
        phone = (phone or "").strip()

        if not name:
            raise ValidationError("Student name cannot be empty.")
        if not department:
            raise ValidationError("Department cannot be empty.")
        if not phone.isdigit() or len(phone) < 10:
            raise ValidationError("Phone number must be at least 10 digits.")
        if "@" not in email or "." not in email:
            raise ValidationError("Invalid email format.")
        try:
            marks = float(marks)
        except (TypeError, ValueError):
            raise ValidationError("Marks must be a number.")
        if not (0 <= marks <= 100):
            raise ValidationError("Marks must be between 0 and 100.")
        if category not in VALID_CATEGORIES:
            raise InvalidCategoryError(
                f"Category must be one of {VALID_CATEGORIES}."
            )

        if self.check_duplicate(name, phone):
            raise DuplicateApplicationError(
                f"Duplicate application detected for '{name}' with phone {phone}."
            )

        student_id = self.next_id
        record = {
            "id": student_id,
            "name": name,
            "marks": marks,
            "category": category,
            "department": department,
            "email": email,
            "phone": phone,
            "eligible": None,
            "status": "Applied",   # Applied -> Admitted / Waitlisted / Rejected
            "applied_on": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        self.students[student_id] = record
        self._insert_sorted_id(student_id)
        self.duplicate_set.add((name.lower(), phone))
        self.department_index[department].append(student_id)
        self.next_id += 1

        return student_id

    # ---------------------- MODULE 2: check_eligibility ----------------------
    def check_eligibility(self, student_id):
        rec = self.students.get(student_id)
        if rec is None:
            raise StudentNotFoundError(f"No student found with ID {student_id}.")
        eligible = rec["marks"] >= MIN_ELIGIBILITY_MARKS
        rec["eligible"] = eligible
        return eligible

    # ---------------------- MODULE 3: check_duplicate ----------------------
    def check_duplicate(self, name, phone):
        key = ((name or "").strip().lower(), (phone or "").strip())
        return key in self.duplicate_set

    # ---------------------- MODULE 4: generate_merit_list ----------------------
    def generate_merit_list(self, department=None, category=None):
        pool = list(self.students.values())
        if department:
            pool = [r for r in pool if r["department"].lower() == department.lower()]
        if category:
            pool = [r for r in pool if r["category"] == category]
        # Only rank students who have been marked eligible
        pool = [r for r in pool if r.get("eligible")]
        if not pool:
            return []
        return self._merge_sort(pool, key=lambda r: r["marks"])

    # ---------------------- MODULE 5: search_student ----------------------
    def search_student(self, student_id):
        try:
            student_id = int(student_id)
        except (TypeError, ValueError):
            raise ValidationError("Student ID must be an integer.")

        found = self._binary_search(student_id)
        if not found or student_id not in self.students:
            raise StudentNotFoundError(f"No student found with ID {student_id}.")
        return self.students[student_id]

    # ---------------------- MODULE 6: search_by_department ----------------------
    def search_by_department(self, department):
        department = (department or "").strip()
        ids = self.department_index.get(department)
        if not ids:
            # case-insensitive fallback
            for dept_key in self.department_index:
                if dept_key.lower() == department.lower():
                    ids = self.department_index[dept_key]
                    break
        if not ids:
            return []
        return [self.students[i] for i in ids if i in self.students]

    # ---------------------- MODULE 7: allocate_seats ----------------------
    def allocate_seats(self):
        """Category-wise seat allocation using a max-heap (priority queue)
        ordered by marks. Students beyond quota go to the waitlist queue."""
        results = defaultdict(list)

        for category in VALID_CATEGORIES:
            quota = self.seat_quota.get(category, 0)
            candidates = [
                r for r in self.students.values()
                if r["category"] == category and r.get("eligible") and r["status"] == "Applied"
            ]
            if not candidates:
                continue

            heap = [(-r["marks"], r["id"]) for r in candidates]
            heapq.heapify(heap)

            allocated = 0
            while heap and allocated < quota:
                neg_marks, sid = heapq.heappop(heap)
                self.students[sid]["status"] = "Admitted"
                self.seats_filled[category] += 1
                results[category].append(sid)
                allocated += 1

            # remaining candidates go to waitlist, still ordered by marks
            while heap:
                neg_marks, sid = heapq.heappop(heap)
                self.students[sid]["status"] = "Waitlisted"
                self.waitlist_queues[category].append(sid)

        return dict(results)

    # ---------------------- MODULE 8: process_waitlist ----------------------
    def process_waitlist(self, category, freed_seats=1):
        if category not in VALID_CATEGORIES:
            raise InvalidCategoryError(f"Category must be one of {VALID_CATEGORIES}.")
        try:
            freed_seats = int(freed_seats)
        except (TypeError, ValueError):
            raise ValidationError("Freed seats must be an integer.")
        if freed_seats <= 0:
            raise ValidationError("Freed seats must be positive.")

        moved = []
        queue = self.waitlist_queues[category]
        while queue and freed_seats > 0:
            sid = queue.popleft()   # FIFO — earliest-waitlisted, highest-marks-first order preserved
            if sid in self.students:
                self.students[sid]["status"] = "Admitted"
                self.seats_filled[category] += 1
                moved.append(sid)
                freed_seats -= 1
        return moved

    # ---------------------- MODULE 9: generate_report ----------------------
    def generate_report(self):
        total = len(self.students)
        admitted = [r for r in self.students.values() if r["status"] == "Admitted"]
        waitlisted = [r for r in self.students.values() if r["status"] == "Waitlisted"]

        avg_marks = round(sum(r["marks"] for r in self.students.values()) / total, 2) if total else 0
        topper = max(self.students.values(), key=lambda r: r["marks"], default=None)

        dept_breakdown = defaultdict(int)
        cat_breakdown = defaultdict(int)
        for r in self.students.values():
            dept_breakdown[r["department"]] += 1
            cat_breakdown[r["category"]] += 1

        return {
            "total_applications": total,
            "total_admitted": len(admitted),
            "total_waitlisted": len(waitlisted),
            "average_marks": avg_marks,
            "topper": {"id": topper["id"], "name": topper["name"], "marks": topper["marks"]} if topper else None,
            "department_breakdown": dict(dept_breakdown),
            "category_breakdown": dict(cat_breakdown),
        }

    # ---------------------- MODULE 10: save_data / load_data ----------------------
    def save_data(self):
        payload = {
            "students": self.students,
            "next_id": self.next_id,
            "seats_filled": dict(self.seats_filled),
            "waitlist_queues": {k: list(v) for k, v in self.waitlist_queues.items()},
        }
        try:
            with open(self.data_file, "w") as f:
                json.dump(payload, f, indent=2)
        except IOError as e:
            raise IOError(f"Failed to save data: {e}")

    def load_data(self):
        if not os.path.exists(self.data_file):
            return  # fresh start, nothing to load
        try:
            with open(self.data_file, "r") as f:
                payload = json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            print(f"[Warning] Could not load existing data ({e}). Starting fresh.")
            return

        try:
            raw_students = payload.get("students", {})
            # JSON keys are always strings — convert back to int
            self.students = {int(k): v for k, v in raw_students.items()}
            self.next_id = payload.get("next_id", 1)
            self.seats_filled = defaultdict(int, payload.get("seats_filled", {}))
            self.waitlist_queues = defaultdict(deque)
            for cat, ids in payload.get("waitlist_queues", {}).items():
                self.waitlist_queues[cat] = deque(ids)
            self._rebuild_indexes()
        except (KeyError, ValueError, TypeError) as e:
            print(f"[Warning] Data file was corrupted or malformed ({e}). Starting fresh.")
            self.students = {}
            self.next_id = 1


# --------------------------------------------------------------------------
# TERMINAL MENU / CLI
# --------------------------------------------------------------------------
def prompt(text):
    return input(text).strip()


def print_student(rec):
    print(f"  ID: {rec['id']} | Name: {rec['name']} | Marks: {rec['marks']} | "
          f"Category: {rec['category']} | Dept: {rec['department']} | "
          f"Status: {rec['status']} | Eligible: {rec.get('eligible')}")


def run_menu(system: AdmissionSystem):
    MENU = """
==================== COLLEGE ADMISSION MANAGEMENT SYSTEM ====================
 1. Add New Application
 2. Check Eligibility
 3. Check Duplicate (manual check)
 4. Generate Merit List
 5. Search Student by ID
 6. Search by Department
 7. Allocate Seats (category-wise, quota-based)
 8. Process Waitlist
 9. Generate Admission Report
10. Save Data
11. View All Students
 0. Save & Exit
===============================================================================
"""
    while True:
        print(MENU)
        choice = prompt("Enter choice: ")

        try:
            if choice == "1":
                name = prompt("Name: ")
                marks = prompt("Marks (0-100): ")
                print(f"Categories: {VALID_CATEGORIES}")
                category = prompt("Category: ")
                department = prompt("Department: ")
                email = prompt("Email: ")
                phone = prompt("Phone: ")
                sid = system.add_application(name, marks, category, department, email, phone)
                print(f"[OK] Student '{name}' added successfully with ID {sid}.")

            elif choice == "2":
                sid = int(prompt("Student ID: "))
                eligible = system.check_eligibility(sid)
                print(f"[OK] Eligible for Admission." if eligible else "[OK] Not Eligible for Admission.")

            elif choice == "3":
                name = prompt("Name: ")
                phone = prompt("Phone: ")
                is_dup = system.check_duplicate(name, phone)
                print("[OK] Duplicate record found." if is_dup else "[OK] No duplicate record found.")

            elif choice == "4":
                dept = prompt("Filter by department (leave blank for all): ") or None
                cat = prompt("Filter by category (leave blank for all): ") or None
                merit_list = system.generate_merit_list(dept, cat)
                if not merit_list:
                    print("[INFO] No eligible students found for the given filters.")
                else:
                    print(f"[OK] Merit List Generated Successfully ({len(merit_list)} students):")
                    for rank, rec in enumerate(merit_list, start=1):
                        print(f"  Rank {rank}: ID {rec['id']} - {rec['name']} - {rec['marks']} marks")

            elif choice == "5":
                sid = prompt("Student ID: ")
                rec = system.search_student(sid)
                print(f"[OK] Student Found:")
                print_student(rec)

            elif choice == "6":
                dept = prompt("Department: ")
                results = system.search_by_department(dept)
                print(f"[OK] {dept}: {len(results)} Students Found.")
                for rec in results:
                    print_student(rec)

            elif choice == "7":
                results = system.allocate_seats()
                if not results:
                    print("[INFO] No eligible applicants available for allocation. "
                          "Run 'Check Eligibility' on students first.")
                else:
                    print("[OK] Seat Allocation Complete:")
                    for cat, ids in results.items():
                        print(f"  {cat}: {len(ids)} seats allocated -> IDs {ids}")

            elif choice == "8":
                print(f"Categories: {VALID_CATEGORIES}")
                cat = prompt("Category: ")
                freed = prompt("Number of freed seats: ")
                moved = system.process_waitlist(cat, freed)
                if moved:
                    print(f"[OK] Waitlisted Student(s) Moved to Confirmed: {moved}")
                else:
                    print("[INFO] No students in waitlist for this category.")

            elif choice == "9":
                report = system.generate_report()
                print("[OK] Admission Report:")
                print(f"  Total Applications : {report['total_applications']}")
                print(f"  Total Admitted      : {report['total_admitted']}")
                print(f"  Total Waitlisted    : {report['total_waitlisted']}")
                print(f"  Average Marks       : {report['average_marks']}")
                if report["topper"]:
                    t = report["topper"]
                    print(f"  Topper              : {t['name']} (ID {t['id']}, {t['marks']} marks)")
                print(f"  Department-wise     : {report['department_breakdown']}")
                print(f"  Category-wise       : {report['category_breakdown']}")

            elif choice == "10":
                system.save_data()
                print("[OK] Data Saved Successfully.")

            elif choice == "11":
                if not system.students:
                    print("[INFO] No students in the system yet.")
                for rec in system.students.values():
                    print_student(rec)

            elif choice == "0":
                system.save_data()
                print("[OK] Data Saved Successfully. Goodbye.")
                break

            else:
                print("[ERROR] Invalid choice. Please select a valid menu option.")

        except (ValidationError, InvalidCategoryError, DuplicateApplicationError,
                StudentNotFoundError) as e:
            print(f"[ERROR] {e}")
        except ValueError:
            print("[ERROR] Invalid input type. Expected a number where applicable.")
        except IOError as e:
            print(f"[ERROR] File error: {e}")
        except Exception as e:
            print(f"[ERROR] Unexpected error: {e}")


def run_auth(auth: AuthManager):
    if not auth.admin_exists():
        print("No admin account found. Let's set one up first.\n")
        while True:
            try:
                username = prompt("Choose admin username: ")
                password = prompt("Choose admin password: ")
                auth.register_admin(username, password)
                print("[OK] Admin account created successfully.\n")
                break
            except ValidationError as e:
                print(f"[ERROR] {e}")
            except IOError as e:
                print(f"[ERROR] {e}")

    attempts = 0
    while attempts < auth.max_attempts:
        username = prompt("Admin Username: ")
        password = prompt("Admin Password: ")
        try:
            auth.login(username, password)
            print("[OK] Login successful.\n")
            return True
        except AuthenticationError as e:
            attempts += 1
            remaining = auth.max_attempts - attempts
            print(f"[ERROR] {e} ({remaining} attempt(s) remaining)")

    print("[ERROR] Too many failed attempts. Exiting.")
    return False


def main():
    print("Starting College Admission Management System...\n")
    auth = AuthManager()

    if not run_auth(auth):
        return

    system = AdmissionSystem()
    try:
        run_menu(system)
    except KeyboardInterrupt:
        print("\n[INFO] Interrupted. Saving data before exit...")
        try:
            system.save_data()
            print("[OK] Data saved. Goodbye.")
        except IOError as e:
            print(f"[ERROR] Could not save data: {e}")


if __name__ == "__main__":
    main()