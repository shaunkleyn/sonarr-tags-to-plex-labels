# for VS Code install packages using `py -m pip install arrapi` and `py -m pip install plexapi`
from arrapi import SonarrAPI
from plexapi.server import PlexServer
import re
import configparser
import sys
import logging

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

tvdb_id_to_process = None
library_name = plex_library

# label statuses
COMPLETE = 'Complete'
INCOMPLETE = 'Incomplete'
INPROGRESS = 'InProgress'

# Icons used for printing output while processing shows
label_icons = {
    COMPLETE : '🟢',
    INCOMPLETE : '🔴',
    INPROGRESS : '🔵'
}

season_labels = []



#############
## LOGGING ##
#############
logging.basicConfig(filename='log.txt', level=logging.DEBUG, format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')
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



def getTvdbId(series):
    logger.debug('Extracting TVDB ID')
    tvdb = next((guid for guid in series.guids if guid.id.startswith("tvdb")), None)
    match = re.search(r'\d+', tvdb.id)
    return int(match.group()) if match else 0

def setLabel(media_item, label):
    # Remove all labels that were added prior to changing the casing
    media_item.removeLabel('inprogress').removeLabel('incomplete').removeLabel('complete').addLabel(label)
    season_labels.append(label)

    # Remove all other label labels
    if label == COMPLETE:
        media_item.removeLabel(INPROGRESS).removeLabel(INCOMPLETE)
    elif label == INCOMPLETE:
        media_item.removeLabel(INPROGRESS).removeLabel(COMPLETE)
        incomplete_seasons = True
    elif label == INPROGRESS:
        media_item.removeLabel(INCOMPLETE).removeLabel(COMPLETE)
    
    media_item_title = media_item.title

    # If the media item has a property named "seasonNumber" then we want to display it
    if hasattr(media_item, 'seasonNumber'):
        media_item_title = media_item.parentTitle + ' - ' + media_item_title

    logger.debug('Setting ' + media_item_title + ' as "'  + label + '"')
    logger.info(label_icons[label] + ' ' + label + ' ' + media_item_title)


def getPercentOfEpisodes(sonarr_season):
    logger.debug('Getting episode percentage')
    # If Sonarr says that we have 100% of the episodes then it must mean we have all the aired episodes
    # That doesn't mean we have the entire season as there might still be episodes that are still being aired
    # Sonarr will also report that we have 100% of the season if it's not monitored so if it's not monitored we'll
    # calculate the percentage ourself
    percent_of_episodes = sonarr_season.percentOfEpisodes
    if sonarr_season.monitored == False:
        logger.debug('Season not being monitored')
        logger.debug('Calculating percent of episodes')
        percent_of_episodes = (sonarr_season.episodeFileCount / sonarr_season.totalEpisodeCount) * 100

    logger.debug('Using ' + str(percent_of_episodes) + ' instead of ' + str(sonarr_season.percentOfEpisodes))
    return percent_of_episodes

def getSeasonFromPlex(plex_series, episode_number): 
    logger.debug('Getting season from plex')
    return next((season for season in plex_series.seasons() if int(season.seasonNumber) == episode_number), None)

def isLatestSeason(sonarr_season):
    logger.debug('Check if this is the latest season')
    # Some shows, such as Ancient Aliens, have have seasons missing in Sonarr (for instance it jumps from Season 8 to Season 11)
    # resulting in the `seasonCount` being less than the actual number of seasons, therefore we check if the current 
    # `seasonNumber` is greater or equal to the `seasonCount` to determine if we're looking at the latest season
    return sonarr_season.seasonNumber >= sonarr_series.seasonCount

def contains(array, value):
    for item in array:
        if item == value:
            return True
    return False

if len(sys.argv) > 1:
    logger.debug('TVDB ID "' + str(sys.argv[1]) + '" passed as argument')
    tvdb_id_to_process = sys.argv[1]

# Get all shows from the Plex library
logger.debug('Using library ' + library_name)
plex_series_list = plex.library.section(library_name).all()
for plex_series in plex_series_list:

    # Get the TvDB ID for the show
    tvdb_id = getTvdbId(plex_series)

    # If a TvDB ID has been specified to process a specific show
    # then only continue when we find the show we want to process
    if tvdb_id_to_process is not None and tvdb_id != tvdb_id_to_process:
        continue
    try:
        sonarr_series = sonarr.get_series(tvdb_id=tvdb_id)
    except:
        logger.warn(plex_series.title + ' not found on Sonarr')
        print(plex_series.title + ' not found on Sonarr')

    logger.debug('Processing ' + sonarr_series.title)
    print('Processing ' + sonarr_series.title)

    tagsToSyncToPlex = tagsToSyncToPlexArray.split(',')
    tagsToSyncToPlex = [x.strip().lower() for x in tagsToSyncToPlex]

    # Some series return 0 episodes so ensure that we actually have episodes to check against
    if sonarr_series is not None and len(sonarr_series.tags) > 0:
        # Assume the series is complete
        complete_series = True

        logger.debug('Found ' + str(len(sonarr_series.seasons)) + ' seasons')

        for sonarr_series_tag in sonarr_series.tags:
            if any(filter(None, tagsToSyncToPlex)):
                if tagsToSyncToPlex.count(sonarr_series_tag.label) > 0:
                    # print(sonarr_series_tag.label + " found in list")
                    if not contains(list(map(lambda x:x.tag.lower(),plex_series.labels)), sonarr_series_tag.label):
                        print ('Added ' + sonarr_series_tag.label + ' to ' + sonarr_series.title)
                        plex_series.addLabel(sonarr_series_tag.label)
                # else:
                #      print(sonarr_series_tag.label + " not found in list")
            else:
                print ('no items in array to sycn')

print('Done')

