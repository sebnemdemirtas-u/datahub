import concurrent.futures
import glob
import json
import logging

import pytest
from deepdiff import DeepDiff

import requests_wrapper as requests
from tests.utils import get_gms_url

logger = logging.getLogger(__name__)


@pytest.mark.dependency()
def test_healthchecks(wait_for_healthchecks):
    # Call to wait_for_healthchecks fixture will do the actual functionality.
    pass


def load_tests(fixture_glob="tests/openapi/**/*.json"):
    for test_fixture in glob.glob(fixture_glob):
        with open(test_fixture) as f:
            yield (test_fixture, json.load(f))


def execute_request(request):
    session = requests.Session()
    if "method" in request:
        method = request.pop("method")
    else:
        method = "post"

    url = get_gms_url() + request.pop("url")

    return getattr(session, method)(url, **request)


def evaluate_test(test_name, test_data):
    try:
        for idx, req_resp in enumerate(test_data):
            if "description" in req_resp["request"]:
                description = req_resp["request"].pop("description")
            else:
                description = None
            url = req_resp["request"]["url"]
            actual_resp = execute_request(req_resp["request"])
            try:
                if "response" in req_resp and "status_codes" in req_resp["response"]:
                    assert (
                        actual_resp.status_code in req_resp["response"]["status_codes"]
                    )
                else:
                    assert actual_resp.status_code in [200, 202, 204]
                if "response" in req_resp:
                    if "json" in req_resp["response"]:
                        if "exclude_regex_paths" in req_resp["response"]:
                            exclude_regex_paths = req_resp["response"][
                                "exclude_regex_paths"
                            ]
                        else:
                            exclude_regex_paths = []
                        diff = DeepDiff(
                            actual_resp.json(),
                            req_resp["response"]["json"],
                            exclude_regex_paths=exclude_regex_paths,
                        )
                        assert not diff
                    else:
                        logger.warning("No expected response json found")
            except Exception as e:
                logger.error(
                    f"Error executing step: {idx}, url: {url}, test: {test_name}"
                )
                if description:
                    logger.error(f"Step {idx} Description: {description}")
                logger.error(f"Response content: {actual_resp.content}")
                raise e
    except Exception as e:
        logger.error(f"Error executing test: {test_name}")
        raise e


def run_tests(fixture_glob, num_workers=3):
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = []
        for test_fixture, test_data in load_tests(fixture_glob=fixture_glob):
            futures.append(executor.submit(evaluate_test, test_fixture, test_data))

        for future in concurrent.futures.as_completed(futures):
            logger.info(future.result())


@pytest.mark.dependency(depends=["test_healthchecks"])
def test_openapi_all():
    run_tests(fixture_glob="tests/openapi/**/*.json", num_workers=10)


# @pytest.mark.dependency(depends=["test_healthchecks"])
# def test_openapi_v1():
#     run_tests(fixture_glob="tests/openapi/v1/*.json", num_workers=4)
#
#
# @pytest.mark.dependency(depends=["test_healthchecks"])
# def test_openapi_v2():
#     run_tests(fixture_glob="tests/openapi/v2/*.json", num_workers=4)
#
#
# @pytest.mark.dependency(depends=["test_healthchecks"])
# def test_openapi_v3():
#     run_tests(fixture_glob="tests/openapi/v3/*.json", num_workers=4)
