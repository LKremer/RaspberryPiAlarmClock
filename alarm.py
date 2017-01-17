#!/bin/python3


# stuff for google calendar API:
import httplib2
from apiclient import discovery
from oauth2client import client
from oauth2client.file import Storage

# other dependencies:
import schedule
import vlc

# standard lib:
import datetime
import time
import os
import logging
from logging.handlers import TimedRotatingFileHandler


# some radio urls: https://beebotron.org/index3lite.php?reload
RADIO_URL = 'http://a.files.bbci.co.uk/media/live/manifesto/audio/simulcast/hls/nonuk/sbr_low/ak/bbc_radio_one.m3u8'


# Google calendar API data:
# If modifying these scopes, delete your previously saved credentials
# at ~/.credentials/calendar-python-quickstart.json
SCOPES = 'https://www.googleapis.com/auth/calendar.readonly'
CLIENT_SECRET_FILE = 'client_id.json'
APPLICATION_NAME = 'Raspberry Pi alarm clock'


def get_credentials():
    """
    Gets valid Google Calendar user credentials from storage.
    modified from:
    https://developers.google.com/google-apps/calendar/quickstart/python
    """
    home_dir = os.path.expanduser('~')
    credential_dir = os.path.join(home_dir, '.credentials')
    if not os.path.exists(credential_dir):
        os.makedirs(credential_dir)
    credential_path = os.path.join(credential_dir,
                                   'calendar-python-quickstart.json')

    store = Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
        flow.user_agent = APPLICATION_NAME
        print('Storing credentials to ' + credential_path)
    return credentials


def get_next_alarm_datetime_from_google_calendar():
    """
    Returns the start and end time of the next scheduled alarm event from Google's
    calendar API. Alarm events must be named '[alarm]' without quotes. Returns
    None if there is no upcoming event in the next 24 hours.
    modified from:
    https://developers.google.com/google-apps/calendar/quickstart/python
    """
    credentials = get_credentials()
    http = credentials.authorize(httplib2.Http())
    service = discovery.build('calendar', 'v3', http=http)

    now = datetime.datetime.now()
    query_start = now - datetime.timedelta(hours=12)
    query_stop = now + datetime.timedelta(hours=24)
    eventsResult = service.events().list(
        timeMin=query_start.isoformat() + 'Z', timeMax=query_stop.isoformat() + 'Z',
        calendarId='primary', singleEvents=True, orderBy='startTime').execute()
    events = eventsResult.get('items', [])
    for event in events:
        if event['summary'].strip().lower() == '[alarm]':
            start_and_stop = []
            for start_stop in ('start', 'end'):
                alarm_str_raw = event[start_stop]['dateTime']
                # the google date format is: 2017-01-07T10:00:00+01:00
                alarm_str = alarm_str_raw.strip()[:-6]  # remove the time zone info
                alarm_time = datetime.datetime.strptime(alarm_str, '%Y-%m-%dT%H:%M:%S')
                start_and_stop.append(alarm_time)
            if start_and_stop[1] < now:
                continue  # this event is from the past!
            alarm_time = tuple(start_and_stop)
            break
        else:
            alarm_time = None
    return alarm_time


class Alarm():
    def __init__(self):
        self.mp = None  # music player
        self.next_alarm_datetime = None
        # initialize a rotating logger:
        if not os.path.isdir('logs'):
            os.mkdir('logs')
        log_path = os.path.join('logs', 'log.txt')
        self.logger = logging.getLogger("Rotating Log")
        self.logger.setLevel(logging.INFO)
        handler = TimedRotatingFileHandler(log_path, when="midnight", backupCount=5)
        formatter = logging.Formatter(fmt='%(asctime)s %(levelname)-8s %(message)s',
                                      datefmt='%Y-%m-%d %H:%M:%S')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def tick(self):
        if self.next_alarm_datetime:
            time_left = self.next_alarm_datetime - datetime.datetime.now()
            s = '           {} left until the alarm.            '.format(
                str(time_left).split('.')[0]  # remove seconds decimals
            )
            print(s, end='\r')
        return

    def get_next_alarm_time(self):
        try:
            self.logger.info('Checking Google Calendar for alarm times '
                             'of the next 24 hours...')
            next_alarm_start_stop = \
                get_next_alarm_datetime_from_google_calendar()
        except:
            self.logger.info('Could not access Google calendar, trying again later.')
            next_alarm_start_stop = None
        if next_alarm_start_stop:
            start_time, stop_time = next_alarm_start_stop
            if stop_time != self.next_alarm_datetime:
                self.next_alarm_datetime = stop_time
                music_time = start_time.strftime('%H:%M')
                alarm_time = stop_time.strftime('%H:%M')
                self.logger.info('scheduling music @{}, scheduling alarm @{}'.format(
                    music_time, alarm_time))
                schedule.clear('alarms')
                schedule.every().day.at(music_time).do(self.play_music).tag('alarms')
                schedule.every().day.at(alarm_time).do(self.ring_alarm).tag('alarms')
            else:
                self.logger.info('Already up to date.')
        else:
            self.logger.info('No scheduled alarms were found in the next 24 hours.')
        return

    def play_music(self):
        self.logger.info('Playing music.')
        self.mp = vlc.MediaPlayer(RADIO_URL)
        self.mp.play()
        return

    def stop_music(self):
        self.logger.info('Stopping music.')
        if self.mp:
            self.mp.stop()
        return

    def ring_alarm(self):
        self.stop_music()
        self.logger.info('Playing alarm sound.')
        self.mp = vlc.MediaPlayer('alarm_sounds/annoying.mp3')
        self.mp.play()  # play alarm sound
        schedule.clear('alarms')  # reset alarms
        self.next_alarm_datetime = None
        return


def main():
    a = Alarm()
    a.get_next_alarm_time()
    schedule.every().second.do(a.tick)
    schedule.every().minute.do(a.get_next_alarm_time)

    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == '__main__':
    main()
