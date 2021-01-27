######################################################################################################################
#  Copyright 2020 Amazon.com, Inc. or its affiliates. All Rights Reserved.                                           #
#                                                                                                                    #
#  Licensed under the Apache License, Version 2.0 (the "License"). You may not use this file except in compliance    #
#  with the License. A copy of the License is located at                                                             #
#                                                                                                                    #
#      http://www.apache.org/licenses/LICENSE-2.0                                                                    #
#                                                                                                                    #
#  or in the 'license' file accompanying this file. This file is distributed on an 'AS IS' BASIS, WITHOUT WARRANTIES #
#  OR CONDITIONS OF ANY KIND, express or implied. See the License for the specific language governing permissions    #
#  and limitations under the License.                                                                                #
######################################################################################################################

import logging, uuid, requests
from copy import copy
from crhelper import CfnResource
from datetime import datetime

logger = logging.getLogger(__name__)
helper = CfnResource(json_logging=True, log_level="INFO")


def _sanitize_data(resource_properties):
    # Remove ServiceToken (lambda arn) to avoid sending AccountId
    resource_properties.pop("ServiceToken", None)
    resource_properties.pop("Resource", None)

    # Solution ID and unique ID are sent separately
    resource_properties.pop("SolutionId", None)
    resource_properties.pop("UUID", None)

    return resource_properties


@helper.create
@helper.update
@helper.delete
def custom_resource(event, _):
    request_type = event["RequestType"]
    resource_properties = event["ResourceProperties"]
    resource = resource_properties["Resource"]

    if resource == "UUID" and request_type == "Create":
        random_id = str(uuid.uuid4())
        helper.Data.update({"UUID": random_id})
    elif resource == "AnonymousMetric":
        try:
            metrics_data = _sanitize_data(copy(resource_properties))
            metrics_data["RequestType"] = request_type

            headers = {"Content-Type": "application/json"}
            git_selected = ""
            if len(resource_properties["gitSelected"]) > 0:
                git_selected = "True"
            else:
                git_selected = "False"
            # see if the customer provided an existing S3 bucket name
            existing_bucket_selected = ""
            if len(resource_properties["bucketSelected"]) > 0:
                existing_bucket_selected = "True"
            else:
                existing_bucket_selected = "False"
            payload = {
                "Solution": resource_properties["SolutionId"],
                "gitSelected": git_selected,
                "bucketSelected": existing_bucket_selected,
                "UUID": resource_properties["UUID"],
                "TimeStamp": datetime.utcnow().isoformat(),
                "Data": metrics_data,
            }

            logger.info(f"Sending payload: {payload}")
            response = requests.post("https://metrics.awssolutionsbuilder.com/generic", json=payload, headers=headers)
            logger.info(f"Response from metrics endpoint: {response.status_code} {response.reason}")
        except requests.exceptions.RequestException:
            logger.exception("Could not send usage data")
        except Exception:
            logger.exception("Unknown error when trying to send usage data")


def handler(event, context):
    helper(event, context)
