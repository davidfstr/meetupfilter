# meetupfilter 0.9

## Problem

Tired of being bombarded with "New Meetup Group" emails from [meetup.com]?
Me too. By default meetup.com notifies you of any new groups in your area
matching your interests. However many of these groups never schedule more
than 1 event in their lifetime.

I wanted to additionally filter these notifications such that I was only notified
of new groups that have at least 3 events on their calendar,
showing that they are actually candidates for being an active group.

[meetup.com]: http://meetup.com

## Solution

This script learns about new meetup groups through "New Meetup Group"
emails sent to an IMAP-accessible email account. Whenever these groups
get at least `MIN_EVENTS_TO_ANNOUNCE` meetings on their calendar (if ever),
the script will generate its own summarizing "New Meetup Group" email via SMTP.

These summary emails look like:

```
Subject: New Meetup Groups: Capitol Hill 20s & 30s Games Meetup and 6 other(s)
From: meetupfilter <YOUR_EMAIL@gmail.com>
To: Me <YOUR_EMAIL@gmail.com>

Capitol Hill 20s & 30s Games Meetup
===================================

Play games with other people in their 20s and 30s on Capitol Hill. Bring one game or many. If you don't have a game, just bring yourself!

http://www.meetup.com/Capitol-Hill-20s-30s-Games-Meetup/

[...]

-- 
These new groups matching your interests have at least 3 events on their calendar.

To change which groups are announced and when, change your interests as registered on http://www.meetup.com/ or edit this script.
```

## Requirements

* Python 2.7
* An email account accessible over IMAP where "New Meetup Group" emails from Meetup will be received.
* An email account accessible over SMTP to send summary emails.
* An email address where summary emails will be received.

## Installation

* Create a folder on your IMAP email server to hold "New Meetup Group" emails from Meetup.
    * Create a server-side email rule to move messages with "New Meetup Group" in the subject line from Meetup to the server folder you created.
* Apply for a [Meetup API key]. This is needed when configuring meetupfilter.
* Download the meetupfilter directory to a place on your hard drive. Configure it:
    * Copy the file `meetupfilter_config.tmpl.py` to `meetupfilter_config.py` and fill out the configuration values.
    * Install the [notifymail](https://github.com/davidfstr/notifymail) dependency and [configure it](https://github.com/davidfstr/notifymail#configuration) with the SMTP server for sending summary emails and the destination address where you want to receive the summary emails.
* After you've received at least one regular Meetup email which is routed to the IMAP server folder that you configured, test the meetupfilter script using `python2.7 meetupfilter.py test`.
* Configure cron or some other periodic scheduler to run `python2.7 meetupfilter.py` daily.

[Meetup API key]: http://www.meetup.com/meetup_api/key/

## License

This code is provided under the MIT License.