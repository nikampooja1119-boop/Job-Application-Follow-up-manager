# Job Application Follow-Up Manager

A desktop app built with Python, Tkinter, and MySQL. It helps users keep track of job applications and follow-up dates.

## Features

- Register and log in
- Add, view, edit, and delete job applications
- Search by company, job title, or notes
- Filter applications by status
- View follow-ups due today or overdue
- Export displayed applications to CSV

## Requirements

- Python 3.10 or later
- MySQL Server
- `mysql-connector-python`

Install the MySQL connector from Command Prompt:

```bash
py -m pip install mysql-connector-python
Database setup
1. Open MySQL Command Line Client or MySQL Workbench and sign in.
2. Create a database named job_application_manager.
3. Create two tables:
   - users stores account details and password hashes.
   - applications stores job application details and links each record to its user.
4. Create a MySQL account for the app with permission to read and change records in this database.
5. In main.py, enter your MySQL connection details in the database settings.
6. Run main.py with IDLE or Python, then register and log in.
Application fields
Each application stores the company, job title, application date, status, optional follow-up date, and notes.
Technologies and topics
- Python: variables, conditions, loops, functions, lists, dictionaries, file handling, and exception handling
- Tkinter: forms, labels, entries, buttons, comboboxes, Treeview, search, multiple windows, and message boxes
- MySQL: tables, primary and foreign keys, INSERT, SELECT, UPDATE, DELETE, WHERE, ORDER BY, GROUP BY, and search/filter queries
