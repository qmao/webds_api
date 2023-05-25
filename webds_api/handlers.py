from jupyter_server.base.handlers import APIHandler
from jupyter_server.utils import url_path_join
from swagger_ui import api_doc

import tornado

from .route.route_reprogram        import ProgramHandler
from .route.route_reflash          import ReflashHandler
from .route.route_general          import GeneralHandler
from .route.route_packrat          import PackratHandler
from .route.route_about            import AboutHandler
from .route.route_filesystem       import FilesystemHandler
from .route.route_command          import CommandHandler
from .route.route_report           import ReportHandler
from .route.route_settings         import SettingsHandler
from .route.route_production_tests import ProductionTestsHandler
from .route.route_config           import ConfigHandler
from .route.route_software_update  import SoftwareUpdateHandler
from .route.route_tutor            import TutorHandler
from .route.route_data_collection  import DataCollectionHandler
from .route.route_testrail         import TestrailHandler
from .route.route_register         import RegisterHandler
from .route.route_passthrough      import PassthroughHandler
from .route.route_production_tests_v2 import ProductionTestsV2Handler

def setup_handlers(web_app):
    host_pattern = ".*$"

    base_url = web_app.settings["base_url"]

    general_pattern = url_path_join(base_url, "webds", "general")

    reprogram_pattern = url_path_join(base_url, "webds", "reprogram")

    reflash_pattern = url_path_join(base_url, "webds", "reflash")

    packrat_pattern = url_path_join(base_url, "webds", "packrat" + '(.*)')

    about_pattern = url_path_join(base_url, "webds", "about")

    filesystem_pattern = url_path_join(base_url, "webds", "filesystem")

    command_pattern = url_path_join(base_url, "webds", "command")

    report_pattern = url_path_join(base_url, "webds", "report" + '(.*)')

    settings_pattern = url_path_join(base_url, "webds", "settings/" + '(.*)?' + '(.*)')

    production_tests_pattern = url_path_join(base_url, "webds", "production-tests" + '(.*)')

    config_pattern = url_path_join(base_url, "webds", "config/" + '(.*)')

    software_update_pattern = url_path_join(base_url, "webds", "software-update")

    tutor_pattern = url_path_join(base_url, "webds", "tutor/" + '(.*)')

    data_collection_pattern = url_path_join(base_url, "webds", "data-collection")

    testrail_pattern = url_path_join(base_url, "webds", "testrail/suites" + '(.*)')

    register_pattern = url_path_join(base_url, "webds", "register")

    passthrough_pattern = url_path_join(base_url, "webds", "passthrough/" + '(.*)')

    production_tests_v2_pattern = url_path_join(base_url, "webds", "pt2" + '(.*)')

    handlers = [
                (general_pattern, GeneralHandler),
                (reprogram_pattern, ProgramHandler),
                (packrat_pattern, PackratHandler),
                (about_pattern, AboutHandler),
                (filesystem_pattern, FilesystemHandler),
                (command_pattern, CommandHandler),
                (report_pattern, ReportHandler),
                (settings_pattern, SettingsHandler),
                (production_tests_pattern, ProductionTestsHandler),
                (config_pattern, ConfigHandler),
                (software_update_pattern, SoftwareUpdateHandler),
                (reflash_pattern, ReflashHandler),
                (tutor_pattern, TutorHandler),
                (data_collection_pattern, DataCollectionHandler),
                (testrail_pattern, TestrailHandler),
                (register_pattern, RegisterHandler),
                (passthrough_pattern, PassthroughHandler),
                (production_tests_v2_pattern, ProductionTestsV2Handler),
               ]

    web_app.add_handlers(host_pattern, handlers)

    api_doc(web_app, config_path='/home/dsdkuser/jupyter/workspace/Synaptics/Documentation/WebDS_API/webds_api.yaml', url_prefix='/api/doc', title='API doc')