"""Initialize Fractalis Flask app and configure it.

Modules in this package:
    - config -- Manages Fractalis Flask app configuration
"""
import logging.config

import os
import yaml
from flask import Flask
from flask_cors import CORS
from flask_request_id import RequestID
from redis import StrictRedis

from fractalis.session import RedisSessionInterface

app = Flask(__name__)

# Configure app with defaults
app.config.from_object('fractalis.config')
# Configure app with manually settings
try:
    app.config.from_envvar('FRACTALIS_CONFIG')
    default_config = False
except RuntimeError:
    default_config = True
    pass

# setup logging
with open(os.path.join(os.path.dirname(__file__), 'logging.yaml'), 'rt') as f:
    log_config = yaml.safe_load(f.read())
logging.config.dictConfig(log_config)
log = logging.getLogger(__name__)

# we can't log this earlier because the logger depends on the loaded app config
if default_config:
    log.warning("Environment Variable FRACTALIS_CONFIG not set. Falling back "
                "to default settings. This is not a good idea in production!")

# Plugin that assigns every request an id
RequestID(app)

# create a redis instance
log.info("Creating Redis connection.")
redis = StrictRedis(host=app.config['REDIS_HOST'],
                    port=app.config['REDIS_PORT'],
                    charset='utf-8',
                    decode_responses=True)

# Set new session interface for app
log.info("Replacing default session interface.")
app.session_interface = RedisSessionInterface(redis)

# allow everyone to submit requests
log.info("Setting up CORS.")
CORS(app, supports_credentials=True)

# create celery app
log.info("Creating celery app.")
from fractalis.celeryapp import make_celery, register_tasks  # noqa
celery = make_celery(app)

# register blueprints
from fractalis.analytics.controller import analytics_blueprint  # noqa
from fractalis.data.controller import data_blueprint  # noqa
log.info("Registering Flask blueprints.")
app.register_blueprint(analytics_blueprint, url_prefix='/analytics')
app.register_blueprint(data_blueprint, url_prefix='/data')

# registering all application celery tasks
log.info("Registering celery tasks.")
register_tasks()

log.info("Initialisation of service complete.")

if __name__ == '__main__':
    log.info("Starting builtin web server.")
    app.run()
    log.info("Builtin web server started.")
