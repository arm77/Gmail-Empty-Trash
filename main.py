from __future__ import print_function

import os.path
import sys

# add timeout for token refresh when calling run_local_server
import signal

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from util import Util

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://mail.google.com/']
SENDER_PATTERNS_FILENAME = './sender_patterns.txt'
REGEX_SENDER_PATTERNS_FILENAME = './regex_sender_patterns.txt'
BATCH_SIZE = 50

NORMAL = 'normal'  # default behavior
DRY_RUN = 'dry-run'
IGNORE_FILTER = 'ignore-filter'
INCLUDE_INBOX = 'include-inbox'

LOCAL_SERVER_TIMEOUT_SEC = 60

def get_messages_from_mailbox(messages_client, mailbox):
    results = messages_client.list(userId='me', maxResults=BATCH_SIZE,
                                   labelIds=[mailbox]).execute()
    msgs = results.get('messages', [])
    return list(map(lambda m: messages_client.get(userId='me', id=m['id']).execute(), msgs))


def filter_using_patterns(messages, patterns, regex_patterns, ignore_filter, prefix = ''):
    result = []
    for msg in messages:
        msg_from = filter(
            lambda hdr: hdr['name'].lower() == 'from', msg['payload']['headers'])
        msg_from = list(msg_from)[0]

        if ignore_filter or Util.contains_any(msg_from['value'], patterns, regex_patterns):
            result.append(msg)
            print(f'{prefix} Add : %s' % msg_from['value'])
        else:
            print(f'{prefix} Skip: %s' % msg_from['value'])
    return result

def raise_():
    raise Exception('flow.local_server timeout. Exiting')

def create_messages_client():
    creds = None

    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)

            signal.signal(signal.SIGALRM, lambda sigum, frame: raise_() )
            signal.alarm(LOCAL_SERVER_TIMEOUT_SEC)
            try:
                creds = flow.run_local_server(port=8080, open_browser=False, access_type='offline')
            except Exception as exc:
                print(exc)
                exit(-1)

        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    service = build('gmail', 'v1', credentials=creds)
    return service.users().messages()


def read_sender_patterns_file(pattern_file):
    try:
        return Util.file_lines_to_set(pattern_file)

    except FileNotFoundError as error:
        print('Error: File {0} must exist'.format(pattern_file))
        print(error)
        exit()


def get_and_filter(messages_client, mailbox_name, mode_ignore_filter,
                   sender_patterns, regex_sender_patterns):
    res = []
    if messages := get_messages_from_mailbox(messages_client, mailbox_name):
        res = filter_using_patterns(messages,
            sender_patterns, regex_sender_patterns, mode_ignore_filter, mailbox_name)
    return res


def main(mode_dry_run=True, mode_ignore_filter=False, mode_include_inbox=False):
    messages_client = create_messages_client()
    sender_patterns = read_sender_patterns_file(SENDER_PATTERNS_FILENAME)
    regex_sender_patterns = read_sender_patterns_file(REGEX_SENDER_PATTERNS_FILENAME)

    if not sender_patterns:
        print(SENDER_PATTERNS_FILENAME, 'is empty. Exiting.')
        return

    try:
        num_removed_msgs = 0
        filtered_msgs = []

        for mailbox_name in ('TRASH', 'SPAM', 'INBOX'):
            if mailbox_name == 'INBOX' and not mode_include_inbox:
                continue
            filtered_msgs += get_and_filter(messages_client, mailbox_name,
                mode_ignore_filter or mailbox_name == 'SPAM',
                sender_patterns, regex_sender_patterns)

        if not mode_dry_run and filtered_msgs:
            msg_ids = list(map(lambda m: m['id'], filtered_msgs))
            num_removed_msgs = len(msg_ids)
            messages_client.batchDelete(
                userId='me', body={'ids': msg_ids}).execute()

        if num_removed_msgs:
            print(f'TOTAL: {num_removed_msgs}/{len(filtered_msgs)}')
        print(f'OK ({num_removed_msgs} {"dry-run" if mode_dry_run else "removed"})')

    except HttpError as error:
        print(f'An error occurred: {error}')


if __name__ == '__main__':
    sys.argv.pop(0)
    if sys.argv:
        main(any(x==DRY_RUN for x in sys.argv),
             any(x==IGNORE_FILTER for x in sys.argv),
             any(x==INCLUDE_INBOX for x in sys.argv))
    else:
        main()
