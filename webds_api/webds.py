import getpass
import os

WORKSPACE = os.path.join('/home', getpass.getuser(), 'jupyter/workspace')

# packrat
PACKRAT_CACHE = '/var/cache/syna/packrat'
WORKSPACE_PACKRAT_DIR = os.path.join(WORKSPACE, 'Packrat')
WORKSPACE_PACKRAT_CACHE_DIR = os.path.join(WORKSPACE_PACKRAT_DIR, 'Cache')

# cache
WORKSPACE_CACHE_DIR = os.path.join(WORKSPACE, '.cache')
WORKSPACE_TEMP_FILE = os.path.join(WORKSPACE_CACHE_DIR, 'temp.cache')

# connection settings
CONNECTION_SETTINGS_FILE = '/usr/local/syna/lib/python/touchcomm/connection_params.json'
CONNECTION_SETTINGS_FILE_TEMP = os.path.join(WORKSPACE_CACHE_DIR, 'connection_params.json')

# wifi settings
WIFI_HELPER_PY = '/usr/local/syna/lib/python/system/wlan/wlan_manager.py'

# production tests
PRODUCTION_TEST_JSON_TEMP = os.path.join(WORKSPACE_CACHE_DIR, 'ptset.json.cache')
PRODUCTION_TEST_PY_TEMP = os.path.join(WORKSPACE_CACHE_DIR, 'ptset.py.cache')
PRODUCTION_TEST_LOG_FILE = '/var/log/syna/production_tests.log'
PRODUCTION_TEST_LOG_TEMP = os.path.join(WORKSPACE_CACHE_DIR, 'ptset.log.cache')

# testrail
TESTRAIL_CACHE = '/var/cache/syna/testrail/suites'