from __future__ import print_function

import os.path
import sys

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

#NORMAL = 'normal'  # default behavior
DRY_RUN = 'dry-run'
IGNORE_FILTER = 'ignore-filter'
INCLUDE_INBOX = 'include-inbox'

def get_messages_from_mailbox(messages_client, mailbox):
    results = messages_client.list(userId='me', maxResults=BATCH_SIZE,
                                   labelIds=[mailbox]).execute()
    msgs = results.get('messages', [])
    return list(map(lambda m: messages_client.get(userId='me', id=m['id']).execute(), msgs))


def filter_using_patterns(messages, patterns, regex_patterns, ignore_filter):
    result = []
    for msg in messages:
        msg_from = filter(
            lambda hdr: hdr['name'].lower() == 'from', msg['payload']['headers'])
        msg_from = list(msg_from)[0]

        if ignore_filter or Util.contains_any(msg_from['value'], patterns, regex_patterns):
            result.append(msg)
            print('Add : %s' % msg_from['value'])
        else:
            print('Skip: %s' % msg_from['value'])
    return result

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
            creds = flow.run_local_server(port=8080, open_browser=False, access_type='offline')
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


def main(mode_dry_run=True, mode_ignore_filter=False, mode_include_inbox=False):
    messages_client = create_messages_client()
    sender_patterns = read_sender_patterns_file(SENDER_PATTERNS_FILENAME)
    regex_sender_patterns = read_sender_patterns_file(REGEX_SENDER_PATTERNS_FILENAME)

    if not sender_patterns:
        print(SENDER_PATTERNS_FILENAME, 'is empty. Exiting.')
        return

    try:
        num_filtered_msgs = num_trash_msgs = num_spam_messages = num_inbox_messages = 0
        filtered_msgs = []
        if trash_messages := get_messages_from_mailbox(messages_client, 'TRASH'):
            num_trash_msgs = len(trash_messages)
            print('--- Trash ---')
            filtered_msgs = filter_using_patterns(trash_messages,
                sender_patterns, regex_sender_patterns, mode_ignore_filter)
            num_filtered_msgs = len(filtered_msgs)

        if spam_messages := get_messages_from_mailbox(messages_client, 'SPAM'):
            print('--- Spam ---')
            spam_messages = filter_using_patterns(spam_messages,
                sender_patterns, regex_sender_patterns, True)
            num_spam_messages = len(spam_messages)
            filtered_msgs += spam_messages

        if mode_include_inbox:
            if inbox_messages := get_messages_from_mailbox(messages_client, 'INBOX'):
                print('--- INBOX ---')
                inbox_messages = filter_using_patterns(inbox_messages,
                    sender_patterns, regex_sender_patterns, mode_ignore_filter)
                num_inbox_messages = len(inbox_messages)
                filtered_msgs += inbox_messages

        print(f'Trash+Spam+Inbox-Skip=Delete:' f'{num_trash_msgs}/{num_spam_messages}/'
            f'{num_inbox_messages}/'
            f'{num_trash_msgs - num_filtered_msgs}/{len(filtered_msgs)}')

        if filtered_msgs and not mode_dry_run:
            msg_ids = list(map(lambda m: m['id'], filtered_msgs))
            print(msg_ids)
            messages_client.batchDelete(
                userId='me', body={'ids': msg_ids}).execute()
            print(f'OK ({len(msg_ids)} removed)')
        else:
            print('OK (0 removed - dry-run or nothing to delete)')

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
