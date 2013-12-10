from __future__ import unicode_literals

# ========================================================================================
# General Configuration

MIN_EVENTS_TO_ANNOUNCE = 3

# ========================================================================================
# IMAP Configuration

HOSTNAME = 'imap.gmail.com'
PORT = 993
SSL = True
USER = 'YOUR_EMAIL@gmail.com'
PASSWORD = 'YOUR_PASSWORD'
MAILBOX = '"MAILBOX_WITH_NEW_MEETUP_EMAILS"' # use either 'INBOX' or '"MailboxName"'

# ========================================================================================
# Meetup Configuration

MEETUP_API_KEY = 'cafebabecafebabecafebabecafe'
