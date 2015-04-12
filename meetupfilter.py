from __future__ import unicode_literals

import meetupfilter_config as config
import notifymail
import sys
import traceback

MIN_EVENTS_TO_ANNOUNCE = config.MIN_EVENTS_TO_ANNOUNCE

def main(args):
    try:
        _run_main(args)
    except Exception as e:
        notifymail.send('[meetupfilter] Execution error', traceback.format_exc())

def _run_main(args):
    simulate = 'test' in args
    
    db = open_db()
    
    # Fetch new groups from email.
    # Add to database with status 'new'
    new_group_descs = fetch_new_groups()
    save_groups_as_new(db, new_group_descs)
    
    # Evaluate 'new' groups. If have >= MIN_EVENTS_TO_ANNOUNCE upcoming or past meetups:
    #   1. send announce email
    #   2. transition to state 'announced'
    groups_to_announce = identify_groups_to_announce(db)
    announce_groups(db, groups_to_announce, simulate=simulate)
    if not simulate:
        mark_groups_as_announced(db, groups_to_announce)

# ========================================================================================
# IMAP
# 
# Example source for fetching mail:
# -> http://stackoverflow.com/questions/348630/how-can-i-download-all-emails-with-attachments-from-gmail

import email
import imaplib
import re

HOSTNAME = config.HOSTNAME
PORT = config.PORT
SSL = config.SSL
USER = config.USER
PASSWORD = config.PASSWORD
MAILBOX = config.MAILBOX

def fetch_new_groups():
    """
    Fetches unread "New Meetup Group" emails and returns a list of group
    descriptors for every group announced.
    
    A group descriptor is a dictionary with the keys:
        * urlname
        * title
        * description
    """
    if SSL:
        imap = imaplib.IMAP4_SSL(HOSTNAME, PORT)
    else:
        imap = imaplib.IMAP4(HOSTNAME, PORT)
    imap.login(USER, PASSWORD)
    
    try:
        imap.select(MAILBOX)
        
        print 'Searching for new meetup emails...'
        
        # Get unread messages from Meetup with subject containing "New Meetup"
        (resp, items) = imap.search(None, _pack_search_keys([
            'NOT SEEN',
            'FROM "info@meetup.com"',
            'SUBJECT "New Meetup Group:"',
        ]))
        items = items[0].split()
        
        print 'Downloading %s new meetup emails...' % len(items)
        
        groups = []
        for item in items:
            message = _peek_message(imap, item)
            subject = message['subject'] or '(No subject)'
            
            # Partition message parts by type
            plains = []         # examine with get_payload(decode=True)
            htmls = []          # examine with get_payload(decode=True)
            attachments = []    # examine with get_filename() and get_payload(decode=True)
            others = []
            for part in message.walk():
                is_attachment = part.get('Content-Disposition') is not None
                
                if part.is_multipart():
                    # Skip containers
                    continue
                elif is_attachment:
                    attachments.append(part)
                elif part.get_content_type() == 'text/plain':
                    plains.append(part)
                elif part.get_content_type() == 'text/html':
                    htmls.append(part)
                else:
                    others.append(part)
            
            if len(plains) < 1:
                raise BadMeetupEmailFormat(
                    'Expected at least one text/plain part in message %s.' % repr(subject))
            main_plain_payload = plains[0].get_payload(decode=True)
            
            # HACK: Force decode payload assuming that encoding is UTF-8.
            #       The email.message API provides no easy way to do this.
            if plains[0]['Content-Type'] != 'text/plain; charset=UTF-8':
                raise BadMeetupEmailFormat(
                    'Unexpected content-type %s for the body of message %s.' %
                    (repr(plains[0]['Content-Type']), repr(subject)))
            main_plain_payload = main_plain_payload.decode('utf-8')
            
            m = re.search(r'Check it out!: http://www.meetup.com/([^/]+)/', main_plain_payload)
            if m is None:
                raise BadMeetupEmailFormat(
                    'Unable to locate group URL in body of message %s. Body was %s.' % 
                    (repr(subject), repr(main_plain_payload)))
            group_urlname = m.group(1)
            
            # Prior to 2013-05-18, \r\n was EOL. Now it seems to be \n.
            m = re.search(r'New Meetup Group!\r?\n([^\r\n]+): ([^\r\n]+)\r?\n', main_plain_payload)
            if m is None:
                raise BadMeetupEmailFormat(
                    'Unable to locate group title in body of message %s. Body was %s.' % 
                    (repr(subject), repr(main_plain_payload)))
            group_title = m.group(1)
            
            # Prior to 2013-05-18, \r\n was EOL. Now it seems to be \n.
            # 2015-04-12: Some groups have no description.
            m = re.search(r'(?s)'
                'Check it out!: [^\r\n]*\r?\n'
                '\r?\n'
                '(?:(.*?)\r?\n)?'
                '\r?\n'
                'Related Meetup Groups\r?\n',
                main_plain_payload)
            if m is None:
                raise BadMeetupEmailFormat(
                    'Unable to locate group description in body of message %s. Body was %s.' % 
                    (repr(subject), repr(main_plain_payload)))
            group_description = m.group(1)
            if group_description is None:
                group_description = u''
            
            groups.append({
                'urlname': group_urlname,
                'title': group_title,
                'description': group_description
            })
        
        print 'Marking %s new meetup emails as read...' % len(items)
        
        # Processed all messages successfully. Mark them as read.
        for item in items:
            _mark_as_read(imap, item)
    finally:
        imap.logout()
    
    return groups

def _pack_search_keys(search_keys):
    return '(' + ' '.join(search_keys) + ')'

def _fetch_message(imap, msg_seq_num):
    """
    Fetches the specified message from the current mailbox and
    marks the message as read.
    
    Returns an email.message.Message.
    """
    resp, data = imap.fetch(msg_seq_num, "(RFC822)")    # fetch entire message
    email_body = data[0][1]                             # extract mail content
    
    email_flags_raw = data[1]                           # ex: ' FLAGS (NonJunk \\Seen))'
    email_flags = imaplib.ParseFlags(email_flags_raw)   # ex: ('NonJunk', '\\Seen')
    
    return email.message_from_string(email_body)        # parse

def _peek_message(imap, msg_seq_num):
    """
    Fetches the specified unread message from the current mailbox and
    and leaves the message marked as unread.
    
    Returns an email.message.Message.
    """
    message = _fetch_message(imap, msg_seq_num)
    _mark_as_unread(imap, msg_seq_num)
    return message

def _mark_as_read(imap, msg_seq_num):
    imap.store(msg_seq_num, '+FLAGS', '\\Seen')

def _mark_as_unread(imap, msg_seq_num):
    imap.store(msg_seq_num, '-FLAGS', '\\Seen')

class BadMeetupEmailFormat(Exception):
    pass

# ========================================================================================
# Database

import json
import os
import urllib2
import sqlite3

_DB_FILENAME = 'meetups.sqlite'
DB_FILEPATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), _DB_FILENAME)

# HACK: Relies on garbage collection to close database
def open_db():
    db_exists = os.path.exists(DB_FILEPATH)
    conn = sqlite3.connect(DB_FILEPATH, isolation_level=None) # autocommit
    db = conn.cursor()
    
    if not db_exists:
        db.execute(
            'create table "group" ('
                'urlname text unique not null, '
                'title text not null, '
                'description text not null, '
                'state text not null, '
                'creation_date datetime not null, '
                'announce_date datetime'
            ')')
    
    return db

def save_groups_as_new(db, group_descs):
    if len(group_descs) == 0:
        return
    
    for group_desc in group_descs:
        # Ignore group if it was already inserted
        db.execute('select 1 from "group" where urlname=?', (group_desc['urlname'],))
        if db.fetchone() is not None:
            continue
        
        db.execute(
            'insert into "group" ('
                'urlname, title, description, state, creation_date'
            ') values ('
                '?, ?, ?, ?, datetime("now")'
            ')', (
                group_desc['urlname'],
                group_desc['title'],
                group_desc['description'],
                'new',
            ))

def identify_groups_to_announce(db):
    db.execute('select urlname from "group" where state="new"')
    new_groups = [row[0] for row in db.fetchall()]
    
    print 'Checking status of %s unannounced group(s)...' % len(new_groups)
    
    groups_to_announce = []
    for new_group in new_groups:
        num_events = get_scheduled_event_count_for_group(
            new_group, MIN_EVENTS_TO_ANNOUNCE)
        
        # Groups only become announce-worthy once they have at least a few
        # events on their calendar.
        if num_events >= MIN_EVENTS_TO_ANNOUNCE:
            groups_to_announce.append(new_group)
    
    return groups_to_announce

def load_groups(db, groups):
    if len(groups) == 0:
        return []
    
    db_cols = ['urlname', 'title', 'description']
    db.execute(
        'select ' +
            ','.join(db_cols) +
        ' from "group" where urlname in (' +
            ','.join('?' * len(groups)) +
        ')',
        groups)
    group_descs = [dict(zip(db_cols, row)) for row in db.fetchall()]
    return group_descs

def mark_groups_as_announced(db, groups):
    if len(groups) == 0:
        return
    
    db.execute(
        'update "group" set ' +
            'state="announced", ' +
            'announce_date=datetime("now") ' +
        'where urlname in (' +
            ','.join('?' * len(groups)) +
        ')',
        groups)

# ========================================================================================
# Meetup

MEETUP_API_KEY = config.MEETUP_API_KEY

def get_scheduled_event_count_for_group(group_urlname, max_count=20):
    """
    Returns the number of events on the specified group's calendar.
    
    NOTE: Always returns 0 events for private groups.
    """
    # TODO: Use alternate event-counting method that works for non-private
    #       groups. Perhaps by parsing the meetup.com page.
    events = json.load(urllib2.urlopen(
        'https://api.meetup.com/2/events?'
            'key='+MEETUP_API_KEY+'&'
            'sign=true&'
            'status=upcoming,past&'
            'group_urlname='+group_urlname+'&'
            'page='+str(max_count)))
    num_events = len(events['results'])
    return num_events


# ========================================================================================
# SMTP

import notifymail

def announce_groups(db, groups_to_announce, simulate=False):
    if len(groups_to_announce) == 0:
        print 'No groups to announce.'
        return
    
    group_descs = load_groups(db, groups_to_announce)
    mail = compose_announce_email(group_descs)
    if simulate:
        print mail['body']
    else:
        notifymail.send(mail['subject'], mail['body'], from_name='meetupfilter')
    
    print 'Announced %s group(s).' % len(groups_to_announce)

def compose_announce_email(group_descs):
    if len(group_descs) == 1:
        subject = u'New Meetup Group: %s' % group_descs[0]['title']
    else:
        subject = u'New Meetup Groups: %s and %s other(s)' % (
            group_descs[0]['title'],
            len(group_descs) - 1)
    
    body = u''
    
    for group_desc in group_descs:
        title = group_desc['title']
        description = group_desc['description']
        
        CRLF = u'\r\n'
        body += (
            title + CRLF +
            (u'=' * min(80, len(title))) + CRLF +
            CRLF +
            description + CRLF +
            CRLF +
            u'http://www.meetup.com/' + group_desc['urlname'] + u'/' + CRLF +
            CRLF +
            CRLF)
    
    body += (
        u'-- ' + CRLF +
        u'These new groups matching your interests have at least ' + 
            str(MIN_EVENTS_TO_ANNOUNCE) + ' events on their calendar.' + CRLF +
        u'' + CRLF +
        u'To change which groups are announced and when, change your interests as '
            u'registered on http://www.meetup.com/ or edit this script.' + CRLF)
    
    return {
        'subject': subject,
        'body': body,
    }

# ========================================================================================

if __name__ == '__main__':
    main(sys.argv[1:])
