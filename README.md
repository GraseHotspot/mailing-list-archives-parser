# Grase Hotspot Mailing List Archive Parser

Parse Mbox file of mailing list archives and create Markdown mailing list posts that can be processed into a static archive

Code taken from https://github.com/tombusby/cypherpunk-mailing-list-archive-parser and adapted as needed

This repo parses `grasehotspot/topics.mbox` and creates a bunch of folders that get copied into [https://github.com/GraseHotspot/mailing-list-archives](https://github.com/GraseHotspot/mailing-list-archives) which does the actual hard work of creating the static site.

`grasehotspot/topics.mbox` Has not been commited to the repo as it contains unmasked emails, and at this stage the decision is not to publish full email addresses.

## Transfer to other repo
threads_test -> _months
author_index/authors.md -> authors_by_post.md
authors_test -> _authors
emails_test -> _emails
_years -> _years