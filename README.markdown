# \#GuestCurator

This bot was commissioned by [Curator@mastodon.art][curator] to automate
the re-boosting of another user's boosts over a length of time. The curator first
vets the selected user's boosts and faves the ones they wish to re-boost, then
one toot will be boosted every 25 to 40 minutes.

The bot is entirely controlled by DMing oneself. It was my first attempt at giving a
bot a friendly UI and I think I did OK for a first try 😊 Here is [a video of it in action][v].

[curator]: https://mastodon.art/@Curator
[v]: https://media.chitter.xyz/media_attachments/files/000/109/777/original/a0ec40e4c3ccde60.mp4

## quick and dirty instructions

### check python version

    python -V

should be 3.3+ <small>though really i havent tested anything else than 3.6</small>

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
