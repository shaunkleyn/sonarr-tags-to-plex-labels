# for VS Code install packages using `py -m pip install arrapi` and `py -m pip install plexapi`
# python3 -m venv env  
# source env/bin/activate  
# python3 -m pip install arrapi 
# python3 -m pip install plexapi
from arrapi import SonarrAPI
from plexapi.server import PlexServer
import re
import configparser
import sys
import logging
import os
from datetime import datetime
import datetime
import calendar


config = configparser.ConfigParser()
config.read('config.ini')

# Plex
plex_url = config['plex']['url']
plex_token = config['plex']['token']
plex_library = config['plex']['library']

# Sonarr
sonarr_url = config['sonarr']['url']
sonarr_api_key = config['sonarr']['apikey']
tagsToSyncToPlexArray = config['sonarr']['tagsToSyncToPlex']

plex = PlexServer(plex_url, plex_token)
sonarr = SonarrAPI(sonarr_url, sonarr_api_key)

library_name = plex_library

#############
## LOGGING ##
#############
log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../upcoming_shows.log')
logging.basicConfig(filename=log_file, level=logging.DEBUG, format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')
# create logger
logger = logging.getLogger('')
logger.setLevel(logging.INFO)

# create console handler and set level to debug
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

# create formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# add formatter to ch
ch.setFormatter(formatter)

# add ch to logger
logger.addHandler(ch)



 

 
def rem_time(d):
    s = ''
    s = str(d.year) + '-' + str(d.month) + '-' + str(d.day)
    return s
 
# d = datetime(2022,6,10,16,20,15)
# print(rem_time(d))   

def getTvdbId(series):
    logger.debug('Extracting TVDB ID')
    tvdb = next((guid for guid in series.guids if guid.id.startswith("tvdb")), None)
    match = re.search(r'\d+', tvdb.id)
    return int(match.group()) if match else 0

def contains(array, value):
    for item in array:
        if item == value:
            return True
    return False

def getSeasonFromPlex(plex_series, seasonNumber): 
    logger.debug('Getting season from plex')
    return next((season for season in plex_series.seasons() if int(season.seasonNumber) == seasonNumber), None)

def next_weekday(d, weekday):
    days_ahead = weekday - d.weekday()
    if days_ahead <= 0: # Target day already happened this week
        days_ahead += 7
    return d + datetime.timedelta(days_ahead)

def get_upcoming_from_sonarr():
    upcoming = {}
    all = sonarr.all_series()
    for series in all:
        if series.nextAiring is not None:
            next_airing = series.nextAiring
            #season = series.seasons[-1]
            print(f'{series.title} upcoming {next_airing}')
            key = rem_time(next_airing)

            if upcoming.get(key) is None:
                upcoming[key] = []

            when = ''
            if key == rem_time(datetime.date.today()):
                when = 'LaterToday'
            elif key == rem_time(datetime.date.today() + datetime.timedelta(days=1)):
                when = 'Tomorrow'
            elif next_airing.date() > (datetime.date.today() + datetime.timedelta(days=1)) and next_airing.date() <= next_weekday(datetime.date.today(), 6):
                when = calendar.day_name[next_airing.date().weekday()]
            elif next_airing.date() > next_weekday(datetime.date.today(), 6) and next_airing.date() < next_weekday(datetime.date.today(), 13):
               when = 'NextWeek'

            if when != '':
                upcoming[key].append({'title': series.title, 'tvdb': series.tvdbId, 'when' : 'Upcoming_' + when, 'season_number' : series.seasons[-1].seasonNumber})

            # season = series.seasons[-1]
            # nam = series.seasons[-1]
            # os.makedirs(f"./{series.cleanTitle}/{series.seasons[-1].seasonNumber}", exist_ok=True)

    return upcoming

def clear_upcoming_tags_in_plex():
# Get all shows from the Plex library
    logger.debug('Using library ' + library_name)
    plex_series_list = plex.library.section(library_name).all()
    for plex_series in plex_series_list:
        
        if plex_series.labels is not None and len(plex_series.labels) > 0:
            #for i in plex_series.labels:
                #print(i)

            has_upcoming_label = [i for i in plex_series.labels if i.tag.startswith('Upcoming')]
            if has_upcoming_label is not None and len(has_upcoming_label) > 0:
                for label in has_upcoming_label:
                    plex_series.removeLabel(label)
                    print('Removing label ' + label.tag + ' from ' + plex_series.title)
            
            if hasattr(plex_series, 'seasons'):
                for plex_season in plex_series.seasons():
                    season_labels = [i for i in plex_season.labels if i.tag.startswith('Upcoming')]
                    if season_labels is not None and len(season_labels) > 0:
                        for season_label in season_labels:
                            plex_series.removeLabel(season_label)
                            print('Removing label ' + season_label.tag + ' from ' + plex_series.title + ' Season ' + str(plex_season.seasonNumber))


if len(sys.argv) > 1:
    logger.debug('TVDB ID "' + str(sys.argv[1]) + '" passed as argument')
    tvdb_id_to_process = sys.argv[1]


clear_upcoming_tags_in_plex()

upcoming = get_upcoming_from_sonarr()

keys = list(upcoming.keys())
keys.sort()
# sorted_dict = {i: myDict[i] for i in myKeys}

for key in keys:
    print(upcoming[key])
    for show in upcoming[key]:
        plex_show = plex.library.section(library_name).getGuid('tvdb://' + str(show['tvdb']))
        plex_season = getSeasonFromPlex(plex_show, int(show['season_number']))
        if plex_season is None:
            plex_show.addLabel('Upcoming_NewSeason')
        else:
            plex_show.addLabel('Upcoming')
            plex_season.addLabel(show['when'])


print('Done')

