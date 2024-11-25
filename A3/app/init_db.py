import sqlite3
from random import randrange
from datetime import timedelta, datetime


def random_date(start, end):
    """
    This function will return a random datetime between two datetime
    objects.
    """
    delta = end - start
    int_delta = (delta.days * 24 * 60 * 60) + delta.seconds
    random_second = randrange(int_delta)
    return start + timedelta(seconds=random_second)


d1 = datetime.strptime("1/1/2022 1:30 PM", "%m/%d/%Y %I:%M %p")
d2 = datetime.strptime("1/1/2023 4:50 AM", "%m/%d/%Y %I:%M %p")

timestamp1 = random_date(d1, d2)
timestamp2 = random_date(d1, d2)
timestamp3 = random_date(d1, d2)
timestamp4 = random_date(d1, d2)

connection = sqlite3.connect("database.db")

with open("db/schema.sql") as f:
    connection.executescript(f.read())

cur = connection.cursor()

cur.execute(
    f"INSERT INTO message (person, text, created) VALUES ('Tom', 'Hello, world!', '{timestamp1}')"
)
cur.execute(
    f"INSERT INTO message (person, text, created) VALUES ('Peter', 'I like Pizza', '{timestamp2}')"
)
cur.execute(
    f"INSERT INTO message (person, text, created) VALUES ('Max', 'carpe diem', '{timestamp3}')"
)
cur.execute(
    f"INSERT INTO message (person, text, created) VALUES ('Robert', 'woof', '{timestamp4}')"
)

connection.commit()
connection.close()
