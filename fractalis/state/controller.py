"""The /state controller."""

import re
import json
import logging
from uuid import UUID, uuid4
from typing import Tuple

from flask import Blueprint, jsonify, Response, request, session

from fractalis import redis
from fractalis.validator import validate_json, validate_schema
from fractalis.analytics.task import AnalyticTask
from fractalis.data.etlhandler import ETLHandler
from fractalis.data.controller import get_data_state_for_task_id
from fractalis.state.schema import request_state_access_schema, \
    save_state_schema


state_blueprint = Blueprint('state_blueprint', __name__)
logger = logging.getLogger(__name__)


@state_blueprint.route('', methods=['POST'])
@validate_json
@validate_schema(save_state_schema)
def save_state() -> Tuple[Response, int]:
    """Save given payload to redis, so it can be accessed later on.
    :return: UUID linked to the saved state.
    """
    logger.debug("Received POST request on /state.")
    payload = request.get_json(force=True)
    state = str(payload['state'])
    matches = re.findall('\$.+?\$', state)
    task_ids = [AnalyticTask.parse_value(match)[0] for match in matches]
    task_ids = list(set(task_ids))
    if not matches:
        error = "This state cannot be saved because it contains no data " \
                "task ids. These are used to verify access to the state and " \
                "its potentially sensitive data."
        logger.error(error)
        return jsonify({'error': error}), 400
    descriptors = []
    for task_id in task_ids:
        value = redis.get('data:{}'.format(task_id))
        if value is None:
            error = "Data task id is {} could not be found in redis. " \
                    "State cannot be saved".format(task_id)
            logger.error(error)
            return jsonify({'error': error}), 400
        try:
            data_state = json.loads(value)
            descriptors.append(data_state['meta']['descriptor'])
        except (ValueError, KeyError, TypeError):
            error = "Task with id {} was found in redis but it represents " \
                    "no valid data state. " \
                    "State cannot be saved.".format(task_id)
            return jsonify({'error': error}), 400
    assert len(matches) == len(descriptors)
    meta_state = {
        'state': state,
        'server': payload['server'],
        'handler': payload['handler'],
        'task_ids': task_ids,
        'descriptors': descriptors
    }
    uuid = uuid4()
    redis.set(name='state:{}'.format(uuid), value=json.dumps(meta_state))
    logger.debug("Successfully saved data to redis. Sending response.")
    return jsonify({'state_id': uuid}), 201


@state_blueprint.route('/<uuid:state_id>', methods=['POST'])
@validate_json
@validate_schema(request_state_access_schema)
def request_state_access(state_id: UUID) -> Tuple[Response, int]:
    """Traverse through the state object linked to the given UUID and look for
    data ids. Then attempt to load the data into the current session to verify
    access.
    :param state_id: The id associated with the saved state.
    :return: See redirect target.
    """
    logger.debug("Received POST request on /state/<uuid:state_id>.")
    wait = request.args.get('wait') == '1'
    payload = request.get_json(force=True)
    state_id = str(state_id)
    value = redis.get('state:{}'.format(state_id))
    if not value:
        error = "Could not find state associated with id {}".format(state_id)
        logger.error(error)
        return jsonify({'error': error}), 404
    meta_state = json.loads(value)
    etl_handler = ETLHandler.factory(handler=meta_state['handler'],
                                     server=meta_state['server'],
                                     auth=payload['auth'])
    task_ids = etl_handler.handle(descriptors=meta_state['descriptors'],
                                  data_tasks=session['data_tasks'],
                                  use_existing=True,
                                  wait=wait)

    session['data_tasks'] += task_ids
    session['data_tasks'] = list(set(session['data_tasks']))
    # if all tasks finish successfully we now that session has access to state
    session['state_access'][state_id] = task_ids
    logger.debug("Tasks successfully submitted. Sending response.")
    return jsonify(''), 202


@state_blueprint.route('/<uuid:state_id>', methods=['GET'])
def get_state_data(state_id: UUID) -> Tuple[Response, int]:
    """Check whether every ETL linked to the state_id successfully executed for
    this session. If and only if every ETL successfully completed grant access
    to the state information.
    :param state_id: ID of the state that is requested.
    :return: Previously saved state.
    """
    logger.debug("Received GET request on /state/<uuid:state_id>.")
    wait = request.args.get('wait') == '1'
    state_id = str(state_id)
    meta_state = json.loads(redis.get('state:{}'.format(state_id)))
    if state_id not in session['state_access']:
        error = "Cannot get state. Make sure to submit a POST request " \
                "to this very same URL containing credentials and server " \
                "data to launch access verification. Only after that a GET " \
                "request might or might not return you the saved state."
        logger.error(error)
        return jsonify({'error': error}), 404
    for task_id in session['state_access'][state_id]:
        data_state = get_data_state_for_task_id(task_id=task_id, wait=wait)
        if data_state is not None and data_state['etl_state'] == 'SUBMITTED':
            return jsonify({'message': 'ETLs are still running.'}), 202
        elif data_state is not None and data_state['etl_state'] == 'SUCCESS':
            continue
        else:
            error = "One or more ETLs failed or has unknown status. " \
                    "Assuming no access to saved state."
            logger.error(error)
            return jsonify({'error': error}), 403
    # replace task ids in state with the ids of the freshly loaded data
    for i, task_id in enumerate(meta_state['task_ids']):
        meta_state['state'] = re.sub(pattern=task_id,
                                     repl=session['state_access'][i],
                                     string=meta_state['state'])
    return jsonify({'state': meta_state}), 200
