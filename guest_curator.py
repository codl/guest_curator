import mastodon
import yaml
import re
from textwrap import dedent
from random import shuffle
import random
import threading
from statistics import mean
import time
import argparse

HELP_TEXT = """

Commands:

help
❓ display this help text

start user@example.com
📣 start re-boosting boosts from the provided account

stop
🔇 stop re-boosting

status
💻 displays status
"""

_HTML_TAG_RE = re.compile('<[^>]+>')
def _strip_html_tags(input: str) -> str:
    return _HTML_TAG_RE.sub('', input)

def pp_minutes(minutes):
    minutes = int(minutes)
    if minutes < 1:
        return "less than a minute"
    elif minutes == 1:
        return "1 minute"
    elif minutes < 60:
        return "{} minutes".format(minutes)
    else:
        hours = minutes // 60
        minutes = minutes % 60
        return "{}h {}m".format(hours, minutes)


class GuestCurator(mastodon.StreamListener):

    def __init__(self, api):
        self.api = api

        self.owner = api.account_verify_credentials()

        # we need to keep track of which commands have already been seen,
        # because dms to self tend to generate two events for some reason
        self.seen = list()

        # we keep track of the bot's posts so the user can
        # reply to them directly
        self.statuses = list()

        # post delay in range of minutes
        self.post_delay = range(25, 40)
        # initial post delay in minutes
        self.initial_post_delay = 2

        # this lock is for the queue, next_post_at, and target
        self.lock = threading.RLock()
        self.queue = list()
        self.next_post_at = None
        self.target = None

        self.thread = None
        self.thread_must_stop = None

    def say(self, content: str):
        # insert U+200C ZERO WIDTH NON-JOINER after each @ to ensure we don't
        # mention anyone accidentally
        content = content.replace('@', '@\u200c')

        # same thing for custom emotes
        content = content.replace(':', ':\u200c')

        status = self.api.status_post(content, visibility='direct')
        self.statuses.append(status['id'])
        return status

    def cleanup(self):
        self.reset()
        for status_id in self.statuses:
            try:
                self.api.status_delete(status_id)
            except:
                pass

    def reset(self):
        with self.lock:
            self.queue = list()
            self.target = None
            self.next_post_at = None
            if(self.thread_must_stop):
                self.thread_must_stop.set()
                self.thread_must_stop = None

    def start(self, target_name: str) -> None:
        self.reset()

        results = self.api.account_search(target_name)
        if len(results) < 1:
            self.say("🙅 Couldn't find this account: @{}".format(target_name))
            return
        target = results[0]
        if not target['display_name']:
            target['display_name'] == target['username']

        # retrieve favs
        count = 0
        last_page = None
        favs = set()
        while count < 150:
            if last_page:
                page = self.api.fetch_next(last_page)
            else:
                page = self.api.favourites(limit=40)

            if not page:  # we've run out of favourites
                break

            for status in page:
                if status['reblogged']:
                    continue
                favs.add(status['id'])

            last_page = page
            count += len(page)

        with self.lock:
            count = 0
            last_page = None
            self.queue = list()
            while count < 150:
                if last_page:
                    page = self.api.fetch_next(last_page)
                else:
                    page = self.api.account_statuses(target['id'], limit=40)

                if not page:  # we've run out of favourites
                    break

                for status in page:
                    if status['reblog'] and status['reblog']['id'] in favs:
                        self.queue.append(status['reblog']['id'])

                last_page = page
                count += len(page)

            shuffle(self.queue)

            if len(self.queue) < 1:
                self.say(
                    "🤔 Couldn't find any boosts by {} (@{}) that you have faved. Are you sure you've got the right person?"
                    .format(target['display_name'], target['acct']))
                return self.reset()

            self.say(dedent("""
                🙌 {} (@{}) is the new #GuestCurator!

                {} faved boosts found, will take roughly {} to boost.

                Boosting will start in {}.
                """).format(
                    target['display_name'], target['acct'],
                    len(self.queue),
                    pp_minutes(len(self.queue) * int(mean(self.post_delay))
                               + self.initial_post_delay),
                    pp_minutes(self.initial_post_delay)
                    ))
            self.target = target
            self.next_post_at = time.time() + self.initial_post_delay * 60

        # do thread stuff
        self.thread_must_stop = threading.Event()
        self.thread = threading.Thread(
                target=self.run_boosts,
                args=(self.thread_must_stop,))
        self.thread.start()

    def run_boosts(self, thread_must_stop):
        while True:
            with self.lock:
                next_post_at = self.next_post_at
            while time.time() < next_post_at:
                # time.sleep(next_post_at - time.time + 0.1)
                #if thread_must_stop.wait(next_post_at - time.time()):
                if thread_must_stop.wait(3):
                    return
            with self.lock:
                status = self.queue.pop()
                if not status:
                    return self.reset()
                try:
                    self.api.status_reblog(status)
                    self.next_post_at += random.choice(self.post_delay) * 60
                except Exception as e:
                    # post deleted? whatever
                    raise e
                    pass
                if len(self.queue) == 0:
                    return self.reset()

    def on_update(self, status):
        # statuses are received as html, we need to strip them
        # down to their plain text
        status['content'] = _strip_html_tags(status['content']).lower()

        if (
                status['id'] not in self.seen
                and int(status['account']['id']) == self.owner['id']
                and status['visibility'] == 'direct'
                and len(status['mentions']) == 0
                and (
                    status['content'].split()[0] == '#guestcurator'
                    or (
                        status['in_reply_to_id']
                        and int(status['in_reply_to_id']) in self.statuses
                    )
                )):
            args = status['content'].split()
            if args[0] == '#guestcurator':
                args.pop(0)

            if len(args) < 1 or args[0] == 'help':
                self.say(
                    "✌ Guest Curator Bot reporting in!"
                    + HELP_TEXT
                    + "\n\n"
                    + dedent("""
                        Tip: You can either send commands by messaging yourself with #GuestCurator followed by a command, like this:

                        #GuestCurator status

                        Or you can just reply to any of this bot's messages with a command.
                        """))
            elif len(args) >= 2 and args[0] == 'start':
                self.start(args[1])
            elif args[0] == 'stop':
                with self.lock:
                    if self.target:
                        self.reset()
                        self.say("🚦 Stopped.")
                    else:
                        self.say("🚦 Already stopped.")
            elif args[0] == 'status':
                with self.lock:
                    if self.target:
                        self.say(
                            dedent("""
                            🔄 Running. {} (@{}) is the guest curator.

                            {} posts left to boost. Next boost in {}.
                            """).format(
                                self.target['display_name'], self.target['acct'],
                                len(self.queue),
                                pp_minutes((self.next_post_at - time.time()) // 60)
                            ))
                    else:
                        self.say("🚦 Stopped.")
            else:
                self.say(
                    "🚫 This doesn't look like a command I know, sorry."
                    + HELP_TEXT)

            # cleanup
            self.api.status_delete(status['id'])
            self.seen.append(status['id'])

            # prune seen list
            if len(self.seen) > 30:
                self.seen = self.seen[-20:]


def run():
    parser = argparse.ArgumentParser(
            description='Guest Curator Bot.')
    parser.add_argument(
            '--config', '-c', type=argparse.FileType('r'),
            default='config.yml',
            help='config file location')

    args = parser.parse_args()
    config = yaml.load(args.config)
    args.config.close()

    api = mastodon.Mastodon(
            client_id=config.get('client_key'),
            client_secret=config.get('client_secret'),
            access_token=config.get('access_token'),
            api_base_url=config.get('instance'))

    try:
        guest_curator = GuestCurator(api)
        api.user_stream(guest_curator)
    except KeyboardInterrupt:
        print("cleaning up...")
        guest_curator.cleanup()


if __name__ == '__main__':
    run()
