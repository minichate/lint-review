import logging

from celery import Celery
from flask import Flask, request, Response
from lintreview.config import load_settings
from lintreview.github import get_client, get_lintrc
from lintreview.tasks import process_pull_request

app = Flask('lintreview')

app.config.from_object(load_settings())

log = logging.getLogger(__name__)
celery = Celery('lintreview.tasks')


@app.route('/ping')
def ping():
    return 'pong\n'


@app.route('/review/start', methods=['POST'])
def start_review():
    action = request.json["action"]
    pull_request = request.json["pull_request"]
    number = pull_request["number"]
    base_repo_url = pull_request["base"]["repo"]["git_url"]
    head_repo_url = pull_request["head"]["repo"]["git_url"]
    user = pull_request['base']['repo']['owner']['login']
    repo = pull_request['base']['repo']['name']

    log.debug("Received GitHub pull request notification for "
              "%s %s, (%s) from: %s",
              base_repo_url, number, action, head_repo_url)

    if action not in ("opened", "synchronize"):
        log.info("Ignored '%s' action." % action)
        return Response(status=204)
    gh = get_client(app.config, user, repo)
    try:
        lintrc = get_lintrc(gh)
    except:
        log.warn("Cannot download .lintrc file for '%s', "
                 "skipping lint checks.", base_repo_url)
        return Response(status=204)
    try:
        process_pull_request.delay(user, repo, pull_request['number'], lintrc)
    except:
        log.error('Could not publish job to celery. Make sure its running')
        return Response(status=500)
    return Response(status=204)