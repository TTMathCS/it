# Tech by Math, tutorial 4, exercise E7: book the last seat safely under SERIALIZABLE, retrying when PostgreSQL
# aborts a transaction with a serialization failure (SQLSTATE 40001). Two threads book at the same moment; a barrier
# makes both read the bookings before either inserts, so the conflict happens every run. Which of the two wins
# changes from run to run.
import threading
import psycopg2
import psycopg2.errors

DSN = dict(host="localhost", user="postgres", dbname="postgres")
setup = psycopg2.connect(**DSN)
setup.autocommit = True
cur = setup.cursor()
cur.execute("DROP TABLE IF EXISTS bookings4, flights4")
cur.execute("CREATE TABLE flights4 (id int PRIMARY KEY, seats int NOT NULL)")
cur.execute("CREATE TABLE bookings4 (flight_id int NOT NULL, passenger text NOT NULL)")
cur.execute("INSERT INTO flights4 VALUES (1, 2)")
cur.execute("INSERT INTO bookings4 VALUES (1, 'Cai')")

both_have_read = threading.Barrier(2)
log = []


def book(passenger):
    con = psycopg2.connect(**DSN)
    con.set_session(isolation_level="SERIALIZABLE")
    try:
        attempts(con, passenger)
    finally:
        con.close()


def attempts(con, passenger):
    for attempt in range(1, 6):
        try:
            with con:  # one transaction: commits at the end of the block, rolls back on an error
                c = con.cursor()
                c.execute("SELECT seats FROM flights4 WHERE id = 1")
                seats, = c.fetchone()
                c.execute("SELECT count(*) FROM bookings4 WHERE flight_id = 1")
                booked, = c.fetchone()
                if attempt == 1:
                    both_have_read.wait()
                if booked >= seats:
                    log.append(f"{passenger}, try {attempt}: {booked} of {seats} booked, the flight is full")
                    return
                c.execute("INSERT INTO bookings4 VALUES (1, %s)", (passenger,))
            log.append(f"{passenger}, try {attempt}: booked (saw {booked} of {seats})")
            return
        except psycopg2.errors.SerializationFailure as e:
            log.append(f"{passenger}, try {attempt}: {e.pgcode} {str(e).splitlines()[0]}; trying again")


threads = [threading.Thread(target=book, args=(p,)) for p in ("Ana", "Ben")]
for t in threads:
    t.start()
for t in threads:
    t.join()
for line in log:
    print(line)
cur.execute("SELECT string_agg(passenger, ', ' ORDER BY passenger), count(*) FROM bookings4")
print("bookings:", cur.fetchone())
cur.execute("DROP TABLE bookings4, flights4")
