# packrat
PACKRAT_CACHE = '/var/cache/syna/packrat'
WORKSPACE = '/home/pi/jupyter/workspace'
WORKSPACE_PACKRAT_DIR = WORKSPACE + '/Packrat/Cache'
WORKSPACE_CACHE_DIR = WORKSPACE + '/.cache'
WORKSPACE_TEMP_FILE = WORKSPACE_CACHE_DIR + '/temp.cache'

# connection settings
CONNECTION_SETTINGS_FILE = '/usr/local/syna/lib/python/touchcomm/connection_params.json'
CONNECTION_SETTINGS_FILE_TEMP = WORKSPACE_CACHE_DIR + 'connection_params.json'

# production tests
PRODUCTION_TEST_JSON_TEMP = WORKSPACE_CACHE_DIR + '/ptset.json.cache'