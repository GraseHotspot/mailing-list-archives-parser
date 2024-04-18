#!/bin/bash -ex
rm -r author_index/authors.md authors_test/ emails_test/ json_authors/ json_months/ raw_messages/ threads_test/ _years/
python3 ./parser.py
python3 ./set_author_ids.py
python3 ./build_json_tree.py
python3 ./build_author_index.py
python3 ./make_markdown_files.py
