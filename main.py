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
BATCH_SIZE = 50

DRY_RUN = 'dry-run'
IGNORE_FILTER = 'ignore-filter'

def get_messages_from_mailbox(messages_client, mailbox):
    results = messages_client.list(userId='me', maxResults=BATCH_SIZE,
                                   labelIds=[mailbox]).execute()
    msgs = results.get('messages', [])
    return list(map(lambda m: messages_client.get(userId='me', id=m['id']).execute(), msgs))


def filter_using_patterns(messages, patterns, regex_patterns, ignore_filter):
    result = []
    for msg in messages:
        msg_from = filter(
            lambda hdr: hdr['name'] == 'From', msg['payload']['headers'])
        msg_from = list(msg_from)[0]

        if ignore_filter or Util.contains_any(msg_from['value'], patterns, regex_patterns):
            result.append(msg)
            print('Add : %s' % msg_from['value'])
        else:
            print('Skip: %s' % msg_from['value'])
    return result

def dump_from_headers(messages):
    result = []
    for msg in messages:
        msg_from = list(filter(
            lambda hdr: hdr['name'] == 'From', msg['payload']['headers']))
        if msg_from: 
            msg_from_1 = msg_from[0]
            result.append(msg_from_1['value'])
    for res in result:
        print('Spam:', res)

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
            creds = flow.run_local_server(port=8080, open_browser=False)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    service = build('gmail', 'v1', credentials=creds)
    return service.users().messages()


def read_sender_patterns_file():
    try:
        return Util.file_lines_to_set(SENDER_PATTERNS_FILENAME)

    except FileNotFoundError as error:
        print('Error: File {0} must exist'.format(SENDER_PATTERNS_FILENAME))
        print(error)
        exit()


def main(mode):
    messages_client = create_messages_client()
    sender_patterns = read_sender_patterns_file()
    regex_sender_patterns = []
    regex_sender_patterns.append(r'\".*amorando.*\"\ <')  # amorando enclosed by double quotes followed by email address prefix '<'

    if not sender_patterns:
        print(SENDER_PATTERNS_FILENAME, 'is empty. Exiting.')
        return

    try:
        trash_messages = get_messages_from_mailbox(messages_client, 'TRASH')
        num_trash_msgs = len(trash_messages)
        filtered_msgs = filter_using_patterns(trash_messages, sender_patterns, regex_sender_patterns, mode == IGNORE_FILTER)
        num_filtered_msgs = len(filtered_msgs)

        ignored = num_trash_msgs - num_filtered_msgs

        out_tr = num_trash_msgs
        out_ig = ignored
        #out_d1 = out_tr - out_ig

        out_sp = 0
        if spam_messages := get_messages_from_mailbox(messages_client, 'SPAM'):
            # spam messages not filtered
            dump_from_headers(spam_messages)
            out_sp = len(spam_messages)
            filtered_msgs += spam_messages

        out_dl = len(filtered_msgs)
        print(f'Trash+Spam-Skip=Delete: {out_tr}/{out_sp}/{out_ig}/{out_dl}')

        if filtered_msgs and mode != DRY_RUN:
            msg_ids = list(map(lambda m: m['id'], filtered_msgs))
            print(msg_ids)
            messages_client.batchDelete(
                userId='me', body={'ids': msg_ids}).execute()
            print('OK ({0} removed)'.format(len(msg_ids)))
        else:
            print('OK (0 removed - dry-run or nothing to delete)')

    except HttpError as error:
        print(f'An error occurred: {error}')


if __name__ == '__main__':
    sys.argv.pop(0)
    if sys.argv:
        main(sys.argv[0])
    else:
        main(DRY_RUN)
