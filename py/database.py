from sys import platform

if platform == "linux" or platform == "linux2":
    from pysqlcipher3 import dbapi2 as sqlite3
elif platform == "win32":
    import sqlite3
# elif platform == "darwin":
    # OS X


def _calc_rsa_length(rsa_bit: int) -> int:
    """
    Calculates the length of the RSA key.

    :param rsa_bit: indicates how many bits of rsa
    :return: returns the length of the rsa key. If -1 means an error.
    """
    if rsa_bit == 4096:
        length = 684
    elif rsa_bit == 3072:
        length = 512
    elif rsa_bit == 2048:
        length = 344
    elif rsa_bit == 1024:
        length = 172
    else:
        length = -1
    return length


def connect_sql(db_dir: str, pwd: str) -> tuple:
    """
    Creates a connection to a database.

    :param db_dir: directory to database
    :param pwd: password to database
    :return: tuple(connection object, cursor object, RSA key length)
    """
    conn = sqlite3.connect(db_dir)
    cur = conn.cursor()
    cur.execute("PRAGMA key = '{}'".format(pwd))
    rsa_bit = cur.execute("""
    SELECT value
    FROM db_information
    WHERE name='rsa_bit'""").fetchone()[0]
    rsa_length = _calc_rsa_length(int(rsa_bit))
    return conn, cur, rsa_length
