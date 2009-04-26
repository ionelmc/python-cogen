"""Pylons environment configuration"""
import os
from mako.lookup import TemplateLookup
from pylons import config

import chatapp.lib.app_globals as app_globals
import chatapp.lib.helpers
from chatapp.config.routing import make_map

def load_environment(global_conf, app_conf):
    """Configure the Pylons environment via the ``pylons.config``
    object
    """
    # Pylons paths
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    paths = dict(root=root,
                 controllers=os.path.join(root, 'controllers'),
                 static_files=os.path.join(root, 'public'),
                 templates=[os.path.join(root, 'templates')])

    # Initialize config with the basic options
    config.init_app(global_conf, app_conf, package='chatapp', paths=paths)

    config['routes.map'] = make_map()
    config['pylons.app_globals'] = app_globals.Globals()
    config['pylons.h'] = chatapp.lib.helpers

    # Create the Mako TemplateLookup, with the default auto-escaping
    config['pylons.app_globals'].mako_lookup = TemplateLookup(
        directories=paths['templates'], input_encoding='utf-8',
        imports=['from webhelpers.html import escape'],
        default_filters=['escape'], output_encoding='utf-8',
        module_directory=os.path.join(app_conf['cache_dir'], 'templates'),
    )

    # CONFIGURATION OPTIONS HERE (note: all config options will override
    # any Pylons config options)
