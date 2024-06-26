#!/usr/bin/env python
import json
import glob
import os
import re
from datetime import datetime
import sqlite3
from shared import make_id_from_email, mask_from


month_file_header = """\
---
layout: default
title: {}
---

# {} {}

_Dates are calculated as the UTC date. The "raw date" from \
the email dump is included in brackets. The date may be inconsistent \
with the raw date because of the time difference with UTC time._

_Ordering by UTC time ensures true chronological ordering._

## Threads

"""


author_file_header = """\
---
layout: default
sender_id: {}
post_count: {}
---

# {} ({} {})

_Be aware that many list participants used multiple email addresses \
over their time active on the list. As such this page may not contain \
all threads available._

## Threads

"""


message_page_template = """\
---
layout: default
title: >
    {}
---

# {} - {}

## Header Data

From: {}<br>
Message Hash: {}<br>
Message ID: {}<br>
Reply To: {}<br>
UTC Datetime: {}<br>
Raw Date: {}<br>

## Raw message

```
{}
```

## Thread

{}
{}
"""


author_index_template = """\
---
layout: default
permalink: /authors/
title: Authors by Number of Posts
---

# Authors by Number of Posts (Highest First)

_Be aware that many list participants used multiple email addresses over \
their time active on the list. As such an email address page may not contain \
all threads available for that person._

"""


years_index_template = """\
---
layout: default
---

# {}

Select one of the months below to view a list of threads:

"""


month_name_map = [
    'January',
    'February',
    'March',
    'April',
    'May',
    'June',
    'July',
    'August',
    'September',
    'October',
    'November',
    'December',
]


def escape_chevrons(text):
    if text:
        return text.replace('<', '\\<').replace('>', '\\>')
    else:
        return "_N/A_"


def make_back_to_links(thread):
    def get_months(months, message):
        if not message['date']:
            return []
        parsed_date = datetime.utcfromtimestamp(message['date'])
        months.add((parsed_date.year, parsed_date.month))
        for child in message['children']:
            get_months(months, child)
        return months
    def get_authors(authors, message):
        sender_id = make_id_from_email(message['from'])
        authors.add((sender_id, message['from']))
        for child in message['children']:
            get_authors(authors, child)
        return authors
    months = get_months(set(), thread)
    authors = get_authors(set(), thread)
    link_text = ""
    for year, month in sorted(months):
        link_text += "+ Return to [{} {}](/archive/{}/{})\n".format(
            month_name_map[month - 1],
            year,
            year,
            str(month).zfill(2)
        )
    link_text += "\n"
    for sender_id, email_from in sorted(authors):
        link_text += "+ Return to \"[{}](/authors/{})\"\n".format(
            mask_from(email_from),
            sender_id
        )
    return link_text


def create_message_pages(thread, message=None):
    if not message:
        message = thread
    if message['date']:
        parsed_date = datetime.utcfromtimestamp(message['date'])
        path = "emails_test/{}/".format(parsed_date.strftime('%Y/%m'))
        iso_date = parsed_date.date().isoformat()
        utc_formatted_date = parsed_date.strftime('%Y-%m-%d %H:%M:%S UTC')
        raw_date = message["raw_date"]
    else:
        path = "emails_test/{}/unknown/".format(message['file_year'])
        iso_date = "(Unknown Date)"
        utc_formatted_date = "(Unknown Date)"
        raw_date = "_N/A_"
    if not os.path.exists(path):
        os.makedirs(path)
    thread_tree = make_markdown_thread_tree(thread, message["message_hash"])
    with open("raw_messages/{}/{}.txt".format(
        message['file_year'], message["message_hash"]
    )) as f:
        raw_message = "{% raw  %}" + f.read() + "{% endraw %}"
    with open("{}/{}.md".format(path, message["message_hash"]), "w") as o:
        o.write(message_page_template.format(
            f"{iso_date} - {message['subject']}",
            iso_date,
            message["subject"],
            escape_chevrons(mask_from(message["from"], '@')),
            #escape_chevrons(message["to"]),
            message["message_hash"],
            escape_chevrons(message["message_id"]),
            escape_chevrons(message["reply_to"]),
            utc_formatted_date,
            raw_date,
            raw_message,
            make_back_to_links(thread),
            thread_tree
        ))
    for child in message["children"]:
        create_message_pages(thread, child)


def make_thread_list_item(message, offset, show_link=True):
    def make_link(subject, formatted_date, message_hash):
        return "[{}](/archive/{}/{})".format(
            subject,
            formatted_date,
            message_hash
        )
    if message['date']:
        parsed_date = datetime.utcfromtimestamp(message['date'])
        path = parsed_date.strftime('%Y/%m')
        iso_date = parsed_date.date().isoformat()
    else:
        path = str(message['file_year']) + "/unknown"
        iso_date = "(Unknown Date)"
    if show_link:
        subject = make_link(
            message['subject'],
            path,
            message['message_hash']
        )
    else:
        subject = message['subject']
    return "{}+ {} ({}) - {} - _{}_\n".format(
        "  " * offset,
        iso_date,
        message['raw_date'],
        subject,
        escape_chevrons(mask_from(message['from'], '@'))
    )


def make_markdown_thread_tree(message, message_hash=None, offset=0):
    show_link = message_hash != message['message_hash']
    if message['no_parent']:
        text = "+ _Unknown thread root_\n"
        offset += 1
    else:
        text = ""
    text += make_thread_list_item(message, offset, show_link)
    for child in message['children']:
        text += make_markdown_thread_tree(child, message_hash, offset + 1)
    return text


def make_markdown_thread(thread):
    return "### {}\n{}".format(
        thread['subject'],
        make_markdown_thread_tree(thread)
    )


def build_threads_by_month():
    for filename in glob.glob('json_months/*/*.json'):
        print(filename)
        with open(filename) as f:
            threads = json.loads(f.read())
        regex = "json_months/([0-9]+)/([0-9]+|unknown).json"
        matches = re.match(regex, filename)
        year, month = matches.group(1), matches.group(2)
        if not os.path.exists("threads_test/{}/".format(year)):
            os.makedirs("threads_test/{}/".format(year))
        with open('threads_test/{}/{}.md'.format(
            year,
            month.zfill(2)
        ), 'w') as o:
            if month != "unknown":
                month_name = month_name_map[int(month) - 1]
            else:
                month_name = "(unknown month)"
            o.write(month_file_header.format(
                f"{month_name} {year}",
                month_name,
                year
            ))
            for thread in threads:
                create_message_pages(thread)
                o.write(make_markdown_thread(thread))
                o.write("\n")


def build_years_index():
    if not os.path.exists("_years"):
        os.makedirs("_years")
    years_filenames = glob.glob('json_months/*')
    years = sorted([int(re.match("json_months/([0-9]+)", year_filename).group(1)) for year_filename in glob.glob('json_months/*')])
    for year in years:
        print(year)
        with open('_years/{}.md'.format(year), 'w') as o:
            o.write(years_index_template.format(year))
            months = sorted([re.match('json_months/([0-9]+)/([0-9]+|unknown).json', month_filename).group(2) for month_filename in glob.glob('json_months/{}/*.json'.format(year))], key=int) 
            for month_number in months:
                print(year, month_number)
                if month_number != "unknown":
                    month_name = month_name_map[int(month_number) - 1]
                else:
                    month_name = "(unknown month)"
                o.write('+ [{}](/archive/{}/{})'.format(month_name, year, month_number.zfill(2)))
                o.write("\n")



def build_author_indices():
    if not os.path.exists("authors_test/"):
        os.makedirs("authors_test/")
    for filename in glob.glob('json_authors/*.json'):
        print(filename)
        with open(filename) as f:
            author = json.loads(f.read())
        with open('authors_test/{}.md'.format(author['sender_id']), 'w') as o:
            o.write(author_file_header.format(
                author['sender_id'],
                author['count'],
                mask_from(author['from']),
                author['count'],
                "posts" if author['count'] > 1 else "post"
            ))
            for thread in author['threads']:
                o.write(make_markdown_thread(thread))
                o.write("\n")
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    sql = """
        SELECT
            `from`,
            `sender_id`,
            count(*) AS `messages`
        FROM
            `messages`
        GROUP BY
            `sender_id`
        ORDER BY
            `messages` DESC;
    """
    if not os.path.exists("authors_index/"):
        os.makedirs("authors_index/")    
    with open('author_index/authors.md', 'w') as o:
        o.write(author_index_template)
        for row in cursor.execute(sql):
            o.write("+ [{}](/authors/{}/) - _{} posts_\n".format(
                mask_from(row[0]),
                row[1],
                row[2],
            ))


def main():
    build_threads_by_month()
    build_years_index()
    build_author_indices()


if __name__ == "__main__":
    main()
