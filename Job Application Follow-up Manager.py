import csv
import hashlib
import hmac
import secrets
import tkinter as tk
from datetime import date, datetime
from tkinter import filedialog, messagebox, ttk

import mysql.connector


# These are the MySQL project-account details from our setup.
DB_HOST = "localhost"
DB_USER = "jobapp"
DB_PASSWORD = "followup123"
DB_NAME = "job_application_manager"

STATUSES = ("Applied", "Interview", "Offer", "Rejected", "Withdrawn")
current_user = None


def connect_database():
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )


def make_password_hash(password):
    salt = secrets.token_hex(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), 100000
    ).hex()
    return salt + ":" + password_hash


def check_password(password, saved_value):
    try:
        salt, saved_hash = saved_value.split(":")
        entered_hash = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt.encode(), 100000
        ).hex()
        return hmac.compare_digest(entered_hash, saved_hash)
    except ValueError:
        return False


def show_screen(screen):
    for frame in (welcome_frame, registration_frame, login_frame, dashboard_frame):
        frame.pack_forget()
    screen.pack(fill="both", expand=True, padx=20, pady=15)


def show_registration():
    show_screen(registration_frame)


def show_login():
    show_screen(login_frame)


def show_welcome():
    show_screen(welcome_frame)


def register_account():
    name = name_entry.get().strip()
    email = register_email_entry.get().strip().lower()
    password = register_password_entry.get()

    if not name or not email or not password:
        messagebox.showwarning("Missing information", "Enter your name, email, and password.")
        return

    if "@" not in email:
        messagebox.showwarning("Email problem", "Enter a valid email address.")
        return

    connection = None
    cursor = None

    try:
        connection = connect_database()
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (%s, %s, %s)",
            (name, email, make_password_hash(password))
        )
        connection.commit()

        messagebox.showinfo("Registered", "Your account was saved. Now log in.")
        register_email_entry.delete(0, tk.END)
        register_password_entry.delete(0, tk.END)
        show_login()

    except mysql.connector.IntegrityError:
        messagebox.showerror("Email already used", "An account already uses that email.")

    except mysql.connector.Error as error:
        messagebox.showerror("Database error", str(error))

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def login():
    global current_user

    email = login_email_entry.get().strip().lower()
    password = login_password_entry.get()

    if not email or not password:
        messagebox.showwarning("Missing information", "Enter your email and password.")
        return

    connection = None
    cursor = None

    try:
        connection = connect_database()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            "SELECT user_id, name, email, password_hash FROM users WHERE email = %s",
            (email,)
        )
        user = cursor.fetchone()

        if user and check_password(password, user["password_hash"]):
            current_user = user
            login_email_entry.delete(0, tk.END)
            login_password_entry.delete(0, tk.END)
            welcome_label.config(text="Welcome, " + user["name"])
            show_screen(dashboard_frame)
            refresh_dashboard()
        else:
            messagebox.showerror("Login failed", "Check your email and password.")

    except mysql.connector.Error as error:
        messagebox.showerror("Database error", str(error))

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def logout():
    global current_user
    current_user = None
    show_welcome()


def load_applications():
    connection = None
    cursor = None

    try:
        search_text = search_entry.get().strip()
        selected_status = filter_status.get()

        sql = """
            SELECT application_id, company, job_title, application_date,
                   status, follow_up_date, notes
            FROM applications
            WHERE user_id = %s
        """
        params = [current_user["user_id"]]

        if search_text:
            sql += " AND (company LIKE %s OR job_title LIKE %s OR notes LIKE %s)"
            search_value = "%" + search_text + "%"
            params.extend([search_value, search_value, search_value])

        if selected_status != "All statuses":
            sql += " AND status = %s"
            params.append(selected_status)

        sql += " ORDER BY (follow_up_date IS NULL), follow_up_date, application_date DESC"

        connection = connect_database()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(sql, tuple(params))
        rows = cursor.fetchall()

        for item in application_tree.get_children():
            application_tree.delete(item)

        today = date.today()

        for row in rows:
            follow_up = row["follow_up_date"]
            if follow_up:
                follow_up_text = follow_up.strftime("%Y-%m-%d")
            else:
                follow_up_text = ""

            application_tree.insert(
                "",
                "end",
                iid=str(row["application_id"]),
                values=(
                    row["company"],
                    row["job_title"],
                    row["application_date"].strftime("%Y-%m-%d"),
                    row["status"],
                    follow_up_text,
                    row["notes"] or ""
                ),
                tags=("due",) if follow_up and follow_up <= today
                and row["status"] in ("Applied", "Interview") else ()
            )

    except mysql.connector.Error as error:
        messagebox.showerror("Could not load applications", str(error))

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def refresh_dashboard():
    load_applications()

    connection = None
    cursor = None

    try:
        connection = connect_database()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT status, COUNT(*) AS total
            FROM applications
            WHERE user_id = %s
            GROUP BY status
            ORDER BY status
            """,
            (current_user["user_id"],)
        )
        counts = cursor.fetchall()

        if counts:
            summary = ", ".join(
                row["status"] + ": " + str(row["total"]) for row in counts
            )
        else:
            summary = "No applications yet."

        summary_label.config(text=summary)

        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM applications
            WHERE user_id = %s
              AND follow_up_date <= %s
              AND status IN ('Applied', 'Interview')
            """,
            (current_user["user_id"], date.today())
        )
        due_count = cursor.fetchone()["total"]
        reminder_label.config(
            text="Follow-ups due today or overdue: " + str(due_count)
        )

    except mysql.connector.Error as error:
        messagebox.showerror("Could not refresh dashboard", str(error))

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def get_selected_application():
    selected = application_tree.selection()

    if not selected:
        messagebox.showwarning("Select an application", "Click an application first.")
        return None

    connection = None
    cursor = None

    try:
        connection = connect_database()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT *
            FROM applications
            WHERE application_id = %s AND user_id = %s
            """,
            (int(selected[0]), current_user["user_id"])
        )
        return cursor.fetchone()

    except mysql.connector.Error as error:
        messagebox.showerror("Database error", str(error))
        return None

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def open_application_form(record=None):
    form = tk.Toplevel(window)
    form.title("Edit application" if record else "Add application")
    form.resizable(False, False)

    fields_frame = ttk.Frame(form, padding=15)
    fields_frame.pack()

    ttk.Label(fields_frame, text="Company *").grid(row=0, column=0, sticky="w", pady=5)
    company_input = ttk.Entry(fields_frame, width=35)
    company_input.grid(row=0, column=1, pady=5)

    ttk.Label(fields_frame, text="Job title *").grid(row=1, column=0, sticky="w", pady=5)
    job_input = ttk.Entry(fields_frame, width=35)
    job_input.grid(row=1, column=1, pady=5)

    ttk.Label(fields_frame, text="Application date (YYYY-MM-DD) *").grid(
        row=2, column=0, sticky="w", pady=5
    )
    application_date_input = ttk.Entry(fields_frame, width=35)
    application_date_input.grid(row=2, column=1, pady=5)

    ttk.Label(fields_frame, text="Follow-up date (YYYY-MM-DD)").grid(
        row=3, column=0, sticky="w", pady=5
    )
    follow_up_input = ttk.Entry(fields_frame, width=35)
    follow_up_input.grid(row=3, column=1, pady=5)

    ttk.Label(fields_frame, text="Status").grid(row=4, column=0, sticky="w", pady=5)
    status_input = ttk.Combobox(
        fields_frame, values=STATUSES, state="readonly", width=32
    )
    status_input.grid(row=4, column=1, pady=5)
    status_input.set("Applied")

    ttk.Label(fields_frame, text="Notes").grid(row=5, column=0, sticky="nw", pady=5)
    notes_input = tk.Text(fields_frame, width=27, height=4)
    notes_input.grid(row=5, column=1, pady=5)

    if record:
        company_input.insert(0, record["company"])
        job_input.insert(0, record["job_title"])
        application_date_input.insert(
            0, record["application_date"].strftime("%Y-%m-%d")
        )
        if record["follow_up_date"]:
            follow_up_input.insert(
                0, record["follow_up_date"].strftime("%Y-%m-%d")
            )
        status_input.set(record["status"])
        notes_input.insert("1.0", record["notes"] or "")
    else:
        application_date_input.insert(0, date.today().strftime("%Y-%m-%d"))

    def save_application():
        company = company_input.get().strip()
        job_title = job_input.get().strip()

        if not company or not job_title:
            messagebox.showwarning(
                "Missing information", "Company and job title are required.", parent=form
            )
            return

        try:
            applied_date = datetime.strptime(
                application_date_input.get().strip(), "%Y-%m-%d"
            ).date()

            follow_up_text = follow_up_input.get().strip()
            if follow_up_text:
                follow_up_date = datetime.strptime(follow_up_text, "%Y-%m-%d").date()
            else:
                follow_up_date = None

        except ValueError:
            messagebox.showwarning(
                "Date format",
                "Enter dates as YYYY-MM-DD, for example 2026-10-15.",
                parent=form
            )
            return

        notes = notes_input.get("1.0", "end-1c").strip() or None
        connection = None
        cursor = None

        try:
            connection = connect_database()
            cursor = connection.cursor()

            values = (
                company,
                job_title,
                applied_date,
                status_input.get(),
                follow_up_date,
                notes
            )

            if record:
                cursor.execute(
                    """
                    UPDATE applications
                    SET company=%s, job_title=%s, application_date=%s,
                        status=%s, follow_up_date=%s, notes=%s
                    WHERE application_id=%s AND user_id=%s
                    """,
                    values + (record["application_id"], current_user["user_id"])
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO applications
                        (company, job_title, application_date, status,
                         follow_up_date, notes, user_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    values + (current_user["user_id"],)
                )

            connection.commit()
            form.destroy()
            refresh_dashboard()
            messagebox.showinfo("Saved", "Application saved in MySQL.")

        except mysql.connector.Error as error:
            messagebox.showerror("Could not save application", str(error), parent=form)

        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    ttk.Button(fields_frame, text="Save", command=save_application).grid(
        row=6, column=0, columnspan=2, sticky="ew", pady=(12, 0)
    )


def edit_application():
    record = get_selected_application()
    if record:
        open_application_form(record)


def delete_application():
    selected = application_tree.selection()

    if not selected:
        messagebox.showwarning("Select an application", "Click an application first.")
        return

    if not messagebox.askyesno("Confirm delete", "Delete this application?"):
        return

    connection = None
    cursor = None

    try:
        connection = connect_database()
        cursor = connection.cursor()
        cursor.execute(
            "DELETE FROM applications WHERE application_id=%s AND user_id=%s",
            (int(selected[0]), current_user["user_id"])
        )
        connection.commit()
        refresh_dashboard()
        messagebox.showinfo("Deleted", "Application deleted.")

    except mysql.connector.Error as error:
        messagebox.showerror("Could not delete application", str(error))

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def export_csv():
    rows = application_tree.get_children()

    if not rows:
        messagebox.showinfo("Nothing to export", "There are no displayed applications.")
        return

    path = filedialog.asksaveasfilename(
        defaultextension=".csv",
        filetypes=(("CSV files", "*.csv"),)
    )

    if not path:
        return

    try:
        with open(path, "w", newline="", encoding="utf-8-sig") as output_file:
            writer = csv.writer(output_file)
            writer.writerow(
                ("Company", "Job title", "Applied", "Status", "Follow-up", "Notes")
            )
            for item in rows:
                writer.writerow(application_tree.item(item, "values"))

        messagebox.showinfo("Export complete", "Applications exported to CSV.")

    except OSError as error:
        messagebox.showerror("Could not export", str(error))


# Main window and screens
window = tk.Tk()
window.title("Job Application Follow-Up Manager")
window.geometry("1000x650")
window.minsize(800, 500)

welcome_frame = ttk.Frame(window)
registration_frame = ttk.Frame(window)
login_frame = ttk.Frame(window)
dashboard_frame = ttk.Frame(window)

# Welcome screen
ttk.Label(
    welcome_frame,
    text="Job Application Follow-Up Manager",
    font=("Arial", 18, "bold")
).pack(pady=25)

ttk.Button(
    welcome_frame, text="Register", width=25, command=show_registration
).pack(pady=8)

ttk.Button(
    welcome_frame, text="Login", width=25, command=show_login
).pack(pady=8)

# Registration screen
ttk.Label(registration_frame, text="Create an account", font=("Arial", 16)).pack(pady=12)

ttk.Label(registration_frame, text="Name").pack()
name_entry = ttk.Entry(registration_frame, width=35)
name_entry.pack(pady=4)

ttk.Label(registration_frame, text="Email").pack()
register_email_entry = ttk.Entry(registration_frame, width=35)
register_email_entry.pack(pady=4)

ttk.Label(registration_frame, text="Password").pack()
register_password_entry = ttk.Entry(registration_frame, width=35, show="*")
register_password_entry.pack(pady=4)

ttk.Button(
    registration_frame, text="Save registration", command=register_account
).pack(pady=10)

ttk.Button(registration_frame, text="Back", command=show_welcome).pack()

# Login screen
ttk.Label(login_frame, text="Login", font=("Arial", 16)).pack(pady=12)

ttk.Label(login_frame, text="Email").pack()
login_email_entry = ttk.Entry(login_frame, width=35)
login_email_entry.pack(pady=4)

ttk.Label(login_frame, text="Password").pack()
login_password_entry = ttk.Entry(login_frame, width=35, show="*")
login_password_entry.pack(pady=4)

ttk.Button(login_frame, text="Login", command=login).pack(pady=10)
ttk.Button(login_frame, text="Back", command=show_welcome).pack()

# Dashboard heading and reminders
welcome_label = ttk.Label(dashboard_frame, text="Your applications", font=("Arial", 16, "bold"))
welcome_label.pack(pady=(5, 2))

reminder_label = ttk.Label(dashboard_frame, text="Follow-ups due today or overdue: 0")
reminder_label.pack()

summary_label = ttk.Label(dashboard_frame, text="No applications yet.")
summary_label.pack(pady=4)

# Dashboard buttons
button_frame = ttk.Frame(dashboard_frame)
button_frame.pack(fill="x", pady=8)

ttk.Button(
    button_frame, text="Add application", command=lambda: open_application_form()
).pack(side="left", padx=4)

ttk.Button(
    button_frame, text="Edit selected", command=edit_application
).pack(side="left", padx=4)

ttk.Button(
    button_frame, text="Delete selected", command=delete_application
).pack(side="left", padx=4)

ttk.Button(
    button_frame, text="Export CSV", command=export_csv
).pack(side="right", padx=4)

ttk.Button(
    button_frame, text="Log out", command=logout
).pack(side="right", padx=4)

# Search and filters
filter_frame = ttk.Frame(dashboard_frame)
filter_frame.pack(fill="x", pady=5)

ttk.Label(filter_frame, text="Search").pack(side="left")
search_entry = ttk.Entry(filter_frame, width=30)
search_entry.pack(side="left", padx=5)
search_entry.bind("<KeyRelease>", lambda event: load_applications())

ttk.Label(filter_frame, text="Status").pack(side="left", padx=(12, 4))
filter_status = tk.StringVar(value="All statuses")
status_filter_box = ttk.Combobox(
    filter_frame,
    textvariable=filter_status,
    values=("All statuses",) + STATUSES,
    state="readonly",
    width=18
)
status_filter_box.pack(side="left")
status_filter_box.bind("<<ComboboxSelected>>", lambda event: load_applications())

# Applications table
columns = ("company", "job", "applied", "status", "follow_up", "notes")
application_tree = ttk.Treeview(
    dashboard_frame, columns=columns, show="headings", selectmode="browse"
)

application_tree.heading("company", text="Company")
application_tree.heading("job", text="Job title")
application_tree.heading("applied", text="Applied")
application_tree.heading("status", text="Status")
application_tree.heading("follow_up", text="Follow-up")
application_tree.heading("notes", text="Notes")

application_tree.column("company", width=140)
application_tree.column("job", width=150)
application_tree.column("applied", width=100)
application_tree.column("status", width=100)
application_tree.column("follow_up", width=100)
application_tree.column("notes", width=250)

application_tree.tag_configure("due", background="#fff0dd")
application_tree.pack(fill="both", expand=True, pady=8)

# Show the welcome screen and start the app.
show_screen(welcome_frame)
window.mainloop()
