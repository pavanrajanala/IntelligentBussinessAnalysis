"""
create_admin.py - Make someone an administrator from the command line.

    python create_admin.py you@example.com            # promote an existing account
    python create_admin.py you@example.com "Your Name" # create the account if it does not exist
                                                        (you will be asked for a password)

You can also set ADMIN_EMAILS=you@example.com in .env: that email becomes admin automatically
when it signs up or logs in.
"""

import getpass
import sys

import db
import repo
import security


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    email = sys.argv[1].strip().lower()
    db.init_schema()
    user = repo.get_user_by_email(email)
    if user:
        repo.set_role(user["id"], "admin")
        print(f"{email} is now an administrator.")
        return 0

    name = sys.argv[2] if len(sys.argv) > 2 else "Administrator"
    password = getpass.getpass("Choose a password (8+ characters): ")
    if len(password) < 8:
        print("Password must be at least 8 characters.")
        return 1
    if password != getpass.getpass("Repeat the password: "):
        print("Passwords do not match.")
        return 1
    user = repo.create_user(email, name, security.hash_password(password))
    repo.set_role(user["id"], "admin")
    print(f"Created administrator account for {email}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
