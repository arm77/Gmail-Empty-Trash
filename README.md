# Gmail Empty Trash

Python script to empty Gmail trash using the Gmail API.

## Install

```shell
pip install -r requirements.txt
```

Must enable Gmail API: https://developers.google.com/gmail/api

Then, it's necessary to adjust the `.sample` files with the corresponding information (and remove the `.sample` part of the filename).

## Run

```shell
python main.py
```

**Note**: Use Python 3

## Troubleshooting

### Authenticate for the first time

1. Create the credentials in the Google Cloud web app and setup the `credentials.json` file accordingly.
2. `rm token.json`
3. Run the script, and open in a browser the URL that appears in the console.
4. After going through the Google Auth dialog, you'll reach a page which URL is `localhost`, and if it's running on a server, then it won't be accessible (if it's local, then auth should end successfully).
5. In order to access `localhost`, create an SSH tunnel using `ssh -L 8080:127.0.0.1:8080 USER@REMOTE_HOST -p PORT` (Note: apparently the URL must be `localhost`, or else Google considers it to be insecure and fails).
6. Reload the page in the browser, and you should see `The authentication flow has completed, you may close this window.`.

### Patterns file

Files named 'sender_patterns.txt' and 'regex_sender_patterns.txt' must exist in the same directory as the Python scripts , even if empty.
From: headers are converted to lowercase before being matched to patterns found in these two files.

