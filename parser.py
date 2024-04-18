#!/usr/bin/env python
from email.parser import Parser
from email import policy
import email
import os
import glob
import re
import sqlite3
import dateutil.parser
import hashlib
import pprint

from shared import mask_all_emails


class EmailMessage(object):

    def __init__(self, raw_text):
        m = hashlib.sha256()
        m.update(raw_text.encode("utf-8"))
        self._message_hash = m.hexdigest()
        #self._raw_text = raw_text
        parsed_message = Parser(policy=policy.default).parsestr(raw_text, headersonly=False)        
        body = parsed_message.get_body(preferencelist=('plain', 'html')).get_content()
        self._raw_text = body
        self._raw_date = parsed_message['Date']
        self._parsed_date = self._parse_date_info(self._raw_date)
        self._file_year = self._parsed_date.year
        self._unixtime = self._get_unixtime_from_parsed(self._parsed_date)
        self._message_id = parsed_message['Message-ID']
        self._from = parsed_message['From']
        self._to = parsed_message['To']
        self._subject = parsed_message['Subject']
        self._reply_to = parsed_message['In-Reply-To']

    def _parse_date_info(self, raw_date):
        tzinfos = {
            'EST': -18000,
            'EDT': -14400,
            'CST': -21600,
            'CDT': -18000,
            'MST': -25200,
            'MDT': -21600,
            'PST': -28800,
            'PPE': -25200,  # See note in README.md
            'PDT': -25200,
        }
        try:
            return dateutil.parser.parse(raw_date, tzinfos=tzinfos)
        except ValueError:
            found = re.search("SMTPSun, (.*) for karn", raw_date)
            if found is not None:
                return dateutil.parser.parse(found.group(1), tzinfos=tzinfos)
            else:
                return dateutil.parser.parse(raw_date.upper(), tzinfos=tzinfos)

    def _get_unixtime_from_parsed(self, parsed_date):
        # Don't judge me
        try:
            tzoffset = parsed_date.utcoffset().total_seconds()
        except AttributeError:
            tzoffset = 0
        offset_1970 = parsed_date.strftime("%s")
        # Times are an hour out, don't know why, added an hour to compensate
        return (60 * 60) + int(offset_1970) - int(tzoffset)


def clean_the_slate(conn):
    if not os.path.exists("raw_messages/"):
        os.makedirs("raw_messages/")
    for f in glob.glob('raw_messages/*/*'):
        os.remove(f)
    conn.cursor().execute('CREATE TABLE IF NOT EXISTS "messages" ( \
        	`message_hash`	TEXT NOT NULL UNIQUE, \
            `thread_root`	TEXT, \
            `message_id`	TEXT, \
            `file_year`	INTEGER, \
            `date`	INTEGER, \
            `raw_date`	TEXT, \
            `sender_id`	TEXT, \
            `from`	TEXT, \
            `to`	TEXT, \
            `subject`	TEXT, \
            `reply_to`	TEXT, \
            `no_parent`	INTEGER \
        )')
    conn.cursor().execute("DELETE FROM messages;")
    conn.commit()


def get_messages():
    stringbuffer = ""
    with open("grasehotspot/topics.mbox") as f:
        for line in f:
            if re.match("From \d+\@xxx", line):
                if stringbuffer:
                    yield EmailMessage(stringbuffer)
                stringbuffer = ""
            else:
                stringbuffer += line


def insert_into_db(conn, message):
    def process_possible_unicode(text):
        return str(text)
        try:
            return str(text.decode('utf-8', 'replace'))
        except UnicodeDecodeError:
            return str(text)

    sql = """
        INSERT INTO messages (
            `message_hash`,
            `message_id`,
            `file_year`,
            `date`,
            `raw_date`,
            `from`,
            `to`,
            `subject`,
            `reply_to`
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
    """
    params = [
        message._message_hash,
        message._message_id,
        message._file_year,
        message._unixtime,
        message._raw_date,
        process_possible_unicode(message._from),
        process_possible_unicode(message._to) if message._to else None,
        process_possible_unicode(message._subject),
        message._reply_to
    ]
    try:
        conn.cursor().execute(sql, params)
    except sqlite3.IntegrityError:
        pass
    except sqlite3.ProgrammingError:
        pprint.pprint(params)


def write_message_to_file(message):
    if not os.path.exists(f"raw_messages/{message._file_year}"):
        os.makedirs(f"raw_messages/{message._file_year}")

    with open("raw_messages/{}/{}.txt".format(
        message._file_year, message._message_hash
    ), "w") as f:
        f.write(mask_all_emails(message._raw_text))


def mark_replies_with_no_parent(conn):
    # The OR condition's messages have reply_tos to non-unique message IDs
    # Also, it's clear by looking at the subjects of the reply_tos and the
    # message_ids they correspond to, they're all orphans.
    sql = """
        UPDATE
            `messages`
        SET
            `no_parent` = 1
        WHERE
            (
                `reply_to` IS NOT NULL
                AND `reply_to` NOT IN (
                    SELECT `message_id` FROM `messages`
                )
            )
            OR `reply_to` IN (
                SELECT
                    `message_id`
                FROM
                    `messages`
                GROUP BY
                    `message_id`
                HAVING
                    count(`message_id`) > 1
            );
    """
    conn.cursor().execute(sql)
    conn.commit()


def fix_weird_1999_dates_between_92_and_97(conn):
    sql = """
        UPDATE
            `messages`
        SET
            `raw_date` = NULL,
            `date` = NULL
        WHERE
            `file_year` < 1998
            AND `raw_date` LIKE "%1999%"
    """
    conn.cursor().execute(sql)
    conn.commit()


def fix_genuine_1999_dates(conn):
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            `file_year`, `message_hash`
        FROM
            `messages`
        WHERE
            `raw_date` LIKE '%1999%'
    """)
    for row in cursor.fetchall():
        os.rename(
            "raw_messages/{}/{}.txt".format(row[0], row[1]),
            "raw_messages/1999/{}.txt".format(row[1])
        )
    sql = """
        UPDATE
            `messages`
        SET
            `file_year` = 1999
        WHERE
            `raw_date` LIKE '%1999%'
    """
    conn.cursor().execute(sql)
    conn.commit()


def calculate_thread_roots(conn):
    sql = """
        UPDATE
            `messages`
        SET
            `thread_root` = `message_hash`
        WHERE
            `reply_to` IS NULL
            OR `no_parent` = 1;
    """
    cursor = conn.cursor()
    cursor.execute(sql)
    conn.commit()
    affected_rows = -1
    i = 0
    while affected_rows:
        i += 1
        print(f"Calculating thread_roots, iteration: {i}")
        sql = """
            UPDATE
                `messages`
            SET
                `thread_root` = (
                    SELECT
                        `thread_root`
                    FROM
                        `messages` AS `messages2`
                    WHERE
                        `messages2`.`message_id` = `messages`.`reply_to`
                )
            WHERE
                `reply_to` IN (
                    SELECT
                        `message_id`
                    FROM
                        `messages`
                    WHERE
                        `thread_root` IS NOT NULL
                )
                AND `no_parent` IS NULL
                AND `thread_root` IS NULL
        """
        cursor = conn.cursor()
        cursor.execute(sql)
        affected_rows = cursor.rowcount
        print(f"Affected Rows: {affected_rows}")
    conn.commit()


def main():
    conn = sqlite3.connect('database.db')
    clean_the_slate(conn)
    for message in get_messages():
        insert_into_db(conn, message)
        write_message_to_file(message)
    conn.commit()
    mark_replies_with_no_parent(conn)
    fix_weird_1999_dates_between_92_and_97(conn)
    fix_genuine_1999_dates(conn)
    calculate_thread_roots(conn)
    conn.close()


if __name__ == "__main__":
    main()
