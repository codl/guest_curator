# \#GuestCurator

## quick and dirty instructions

### check python version

    python -V

should be 3.3+

### install dependencies

    python -m venv venv
    venv/bin/pip install -r requirements.txt

### configure

go to your mastodon settings, in the development tab, and create an app

    cp config.example.yml config.yml
    $EDITOR config.yml

feed in your app's various keys

### run

    venv/bin/python guest_curator.py

### use

send a direct message to yourself:

> #GuestCurator help

the bot will reply in a direct message and tell you how to use it
