#######################################################################################################################
#  Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.                                                 #
#                                                                                                                     #
#  Licensed under the Apache License, Version 2.0 (the "License"). You may not use this file except in compliance     #
#  with the License. A copy of the License is located at                                                              #
#                                                                                                                     #
#  http://www.apache.org/licenses/LICENSE-2.0                                                                         #
#                                                                                                                     #
#  or in the 'license' file accompanying this file. This file is distributed on an 'AS IS' BASIS, WITHOUT WARRANTIES  #
#  OR CONDITIONS OF ANY KIND, express or implied. See the License for the specific language governing permissions     #
#  and limitations under the License.                                                                                 #
# #####################################################################################################################
import os
import pytest
import uuid
import json


@pytest.fixture(autouse=True)
def mock_env_variables():
    os.environ["BLUEPRINT_BUCKET_URL"] = "testurl"
    os.environ["NOTIFICATION_EMAIL"] = "test@example.com"
    os.environ["ASSETS_BUCKET"] = "testassetsbucket"
    os.environ["BLUEPRINT_BUCKET"] = "testbucket"
    os.environ["PIPELINE_STACK_NAME"] = "mlops-pipeline"
    os.environ["CFN_ROLE_ARN"] = "arn:aws:role:region:account:action"
    os.environ["IS_MULTI_ACCOUNT"] = "False"
    os.environ["REGION"] = "us-east-1"
    os.environ["ECR_REPO_ARN"] = "test-ecr-repo"
    os.environ["DEV_ACCOUNT_ID"] = "dev_account_id"
    os.environ["STAGING_ACCOUNT_ID"] = "staging_account_id"
    os.environ["PROD_ACCOUNT_ID"] = "prod_account_id"
    os.environ["DEV_ORG_ID"] = "dev_org_id"
    os.environ["STAGING_ORG_ID"] = "staging_org_id"
    os.environ["PROD_ORG_ID"] = "prod_org_id"
    os.environ["MODELARTIFACTLOCATION"] = "model.tar.gz"
    os.environ["INSTANCETYPE"] = "ml.m5.large"
    os.environ["INFERENCEDATA"] = "inference/data.csv"
    os.environ["BATCHOUTPUT"] = "bucket/output"
    os.environ["DATACAPTURE"] = "bucket/datacapture"
    os.environ["TRAININGDATA"] = "model_monitor/training-dataset-with-header.csv"
    os.environ["BASELINEOUTPUT"] = "testbucket/model_monitor/baseline_output2"
    os.environ["SCHEDULEEXP"] = "cron(0 * ? * * *)"
    os.environ["CUSTOMIMAGE"] = "custom/custom_image.zip"
    os.environ["TESTFILE"] = "testfile.zip"
    os.environ["USE_MODEL_REGISTRY"] = "No"
    os.environ["IS_DELEGATED_ADMIN"] = "No"
    os.environ["MODEL_PACKAGE_GROUP_NAME"] = "xgboost"
    os.environ["MODEL_PACKAGE_NAME"] = "arn:aws:sagemaker:*:*:model-package/xgboost/1"


@pytest.fixture
def api_byom_event():
    def _api_byom_event(pipeline_type, is_multi=False, endpint_name_provided=False):
        #  create a map {<attribute_name>: {is_multi (True/False): <parameter-value>}}
        maping = dict(
            inference_instance={
                "True": {
                    "dev": os.environ["INSTANCETYPE"],
                    "staging": os.environ["INSTANCETYPE"],
                    "prod": os.environ["INSTANCETYPE"],
                },
                "False": os.environ["INSTANCETYPE"],
            },
            batch_job_output_location={
                "True": {"dev": "bucket/dev_output", "staging": "bucket/staging_output", "prod": "bucket/prod_output"},
                "False": os.environ["BATCHOUTPUT"],
            },
            data_capture_location={
                "True": {
                    "dev": "bucket/dev_datacapture",
                    "staging": "bucket/staging_datacapture",
                    "prod": "bucket/prod_datacapture",
                },
                "False": os.environ["DATACAPTURE"],
            },
            endpoint_name={
                "True": {
                    "dev": "dev-endpoint",
                    "staging": "staging-endpoint",
                    "prod": "prod-endpoint",
                },
                "False": "test-endpoint",
            },
        )
        event = {
            "pipeline_type": pipeline_type,
            "model_name": "testmodel",
            "model_artifact_location": os.environ["MODELARTIFACTLOCATION"],
            "model_package_name": os.environ["MODEL_PACKAGE_NAME"],
        }
        event["inference_instance"] = maping["inference_instance"][str(is_multi)]

        if pipeline_type in ["byom_batch_builtin", "byom_batch_custom"]:
            event["batch_inference_data"] = os.environ["INFERENCEDATA"]
            event["batch_job_output_location"] = maping["batch_job_output_location"][str(is_multi)]

        if pipeline_type in ["byom_realtime_builtin", "byom_realtime_custom"]:
            event["data_capture_location"] = maping["data_capture_location"][str(is_multi)]
            # add optional endpoint_name
            if endpint_name_provided:
                event["endpoint_name"] = maping["endpoint_name"][str(is_multi)]

        if pipeline_type in ["byom_realtime_builtin", "byom_batch_builtin"]:
            event["model_framework"] = "xgboost"
            event["model_framework_version"] = "0.90-1"
        elif pipeline_type in ["byom_realtime_custom", "byom_batch_custom"]:
            event["custom_image_uri"] = "custom-image-uri"

        return event

    return _api_byom_event


@pytest.fixture
def api_data_quality_event():
    return {
        "pipeline_type": "byom_data_quality_monitor",
        "model_name": "testmodel",
        "endpoint_name": "test_endpoint",
        "baseline_data": os.environ["TRAININGDATA"],
        "baseline_job_output_location": os.environ["BASELINEOUTPUT"],
        "monitoring_output_location": "testbucket/model_monitor/monitor_output",
        "data_capture_location": "testbucket/xgboost/datacapture",
        "schedule_expression": os.environ["SCHEDULEEXP"],
        "instance_type": os.environ["INSTANCETYPE"],
        "instance_volume_size": "20",
        "baseline_max_runtime_seconds": "3600",
        "monitor_max_runtime_seconds": "1800",
    }


@pytest.fixture
def api_model_quality_event(api_data_quality_event):
    model_quality_event = api_data_quality_event.copy()
    model_quality_event.update(
        {
            "pipeline_type": "byom_model_quality_monitor",
            "baseline_inference_attribute": "0",
            "problem_type": "Regression",
            "baseline_ground_truth_attribute": "label",
            "monitor_inference_attribute": "0",
            "monitor_ground_truth_input": "s3://test-bucket/groundtruth",
        }
    )
    return model_quality_event


@pytest.fixture
def api_image_builder_event():
    return {
        "pipeline_type": "byom_image_builder",
        "custom_algorithm_docker": os.environ["CUSTOMIMAGE"],
        "ecr_repo_name": "mlops-ecrrep",
        "image_tag": "tree",
    }


@pytest.fixture
def expected_params_realtime_custom():
    def _expected_params_realtime_custom(endpoint_name_provided=False):
        endpoint_name = "test-endpoint" if endpoint_name_provided else ""
        expected_params = [
            ("AssetsBucket", "testassetsbucket"),
            ("KmsKeyArn", ""),
            ("BlueprintBucket", "testbucket"),
            ("ModelName", "testmodel"),
            ("ModelArtifactLocation", os.environ["MODELARTIFACTLOCATION"]),
            ("InferenceInstance", os.environ["INSTANCETYPE"]),
            ("CustomAlgorithmsECRRepoArn", "test-ecr-repo"),
            ("ImageUri", "custom-image-uri"),
            ("ModelPackageGroupName", ""),
            ("ModelPackageName", os.environ["MODEL_PACKAGE_NAME"]),
            ("DataCaptureLocation", os.environ["DATACAPTURE"]),
            ("EndpointName", endpoint_name),
        ]

        return expected_params

    return _expected_params_realtime_custom


@pytest.fixture
def expected_data_quality_monitor_params():
    return [
        ("BaselineJobName", "test_endpoint-baseline-job-ec3a"),
        ("BaselineOutputBucket", "testbucket"),
        ("BaselineJobOutputLocation", os.environ["BASELINEOUTPUT"]),
        ("DataCaptureBucket", "testbucket"),
        ("DataCaptureLocation", os.environ["BASELINEOUTPUT"]),
        ("EndpointName", "test_endpoint"),
        ("ImageUri", "156813124566.dkr.ecr.us-east-1.amazonaws.com/sagemaker-model-monitor-analyzer"),
        ("InstanceType", os.environ["INSTANCETYPE"]),
        ("InstanceVolumeSize", "20"),
        ("BaselineMaxRuntimeSeconds", "3600"),
        ("MonitorMaxRuntimeSeconds", "1800"),
        ("MonitoringOutputLocation", "testbucket/model_monitor/monitor_output"),
        ("MonitoringScheduleName", "test_endpoint-monitor-2a87"),
        ("ScheduleExpression", os.environ["SCHEDULEEXP"]),
        ("BaselineData", os.environ["TRAININGDATA"]),
    ]


@pytest.fixture
def expected_model_quality_monitor_params(expected_data_quality_monitor_params):
    expected_model_quality = expected_data_quality_monitor_params.copy()

    expected_model_quality.extend(
        [
            ("BaselineInferenceAttribute", "prediction"),
            ("BaselineProbabilityAttribute", "probability"),
            ("BaselineGroundTruthAttribute", "label"),
            ("ProblemType", "Regression"),
            ("MonitorInferenceAttribute", "0"),
            ("MonitorProbabilityAttribute", "0"),
            ("ProbabilityThresholdAttribute", "0.5"),
            ("MonitorGroundTruthInput", "s3://test-bucket/groundtruth"),
        ]
    )

    return expected_model_quality


@pytest.fixture
def expected_common_realtime_batch_params():
    return [
        ("ModelName", "testmodel"),
        ("ModelArtifactLocation", os.environ["MODELARTIFACTLOCATION"]),
        ("InferenceInstance", os.environ["INSTANCETYPE"]),
        ("CustomAlgorithmsECRRepoArn", "test-ecr-repo"),
        ("ImageUri", "custom-image-uri"),
        ("ModelPackageGroupName", ""),
        ("ModelPackageName", os.environ["MODEL_PACKAGE_NAME"]),
    ]


@pytest.fixture
def expected_image_builder_params():
    return [
        ("NotificationEmail", os.environ["NOTIFICATION_EMAIL"]),
        ("AssetsBucket", "testassetsbucket"),
        ("CustomImage", os.environ["CUSTOMIMAGE"]),
        ("ECRRepoName", "mlops-ecrrep"),
        ("ImageTag", "tree"),
    ]


@pytest.fixture
def expected_realtime_specific_params():
    def _expected_realtime_specific_params(endpoint_name_provided=False):
        endpoint_name = "test-endpoint" if endpoint_name_provided else ""
        return [("DataCaptureLocation", os.environ["DATACAPTURE"]), ("EndpointName", endpoint_name)]

    return _expected_realtime_specific_params


@pytest.fixture
def expect_single_account_params_format():
    return {
        "Parameters": {
            "NotificationEmail": os.environ["NOTIFICATION_EMAIL"],
            "AssetsBucket": "testassetsbucket",
            "CustomImage": os.environ["CUSTOMIMAGE"],
            "ECRRepoName": "mlops-ecrrep",
            "ImageTag": "tree",
        }
    }


@pytest.fixture
def stack_name():
    return "teststack-testmodel-byompipelineimagebuilder"


@pytest.fixture
def expected_multi_account_params_format():
    return [
        {"ParameterKey": "NotificationEmail", "ParameterValue": os.environ["NOTIFICATION_EMAIL"]},
        {"ParameterKey": "AssetsBucket", "ParameterValue": "testassetsbucket"},
        {"ParameterKey": "CustomImage", "ParameterValue": os.environ["CUSTOMIMAGE"]},
        {"ParameterKey": "ECRRepoName", "ParameterValue": "mlops-ecrrep"},
        {"ParameterKey": "ImageTag", "ParameterValue": "tree"},
    ]


@pytest.fixture
def expected_batch_specific_params():
    return [
        ("BatchInputBucket", "inference"),
        ("BatchInferenceData", os.environ["INFERENCEDATA"]),
        ("BatchOutputLocation", os.environ["BATCHOUTPUT"]),
    ]


@pytest.fixture
def expected_batch_params():
    return [
        ("AssetsBucket", "testassetsbucket"),
        ("KmsKeyArn", ""),
        ("BlueprintBucket", "testbucket"),
        ("ModelName", "testmodel"),
        ("ModelArtifactLocation", os.environ["MODELARTIFACTLOCATION"]),
        ("InferenceInstance", os.environ["INSTANCETYPE"]),
        ("CustomAlgorithmsECRRepoArn", "test-ecr-repo"),
        ("ImageUri", "custom-image-uri"),
        ("ModelPackageGroupName", ""),
        ("ModelPackageName", os.environ["MODEL_PACKAGE_NAME"]),
        ("BatchInputBucket", "inference"),
        ("BatchInferenceData", os.environ["INFERENCEDATA"]),
        ("BatchOutputLocation", os.environ["BATCHOUTPUT"]),
    ]


@pytest.fixture
def required_api_byom_realtime_builtin():
    def _required_api_byom_realtime_builtin(use_model_registry):
        required_keys = [
            "pipeline_type",
            "model_name",
            "inference_instance",
            "data_capture_location",
        ]
        if use_model_registry == "Yes":
            required_keys.extend(["model_package_name"])
        else:
            required_keys.extend(
                [
                    "model_framework",
                    "model_framework_version",
                    "model_artifact_location",
                ]
            )
        return required_keys

    return _required_api_byom_realtime_builtin


@pytest.fixture
def required_api_byom_batch_builtin():
    return [
        "pipeline_type",
        "model_name",
        "model_artifact_location",
        "inference_instance",
        "batch_job_output_location",
        "model_framework",
        "model_framework_version",
        "batch_inference_data",
    ]


@pytest.fixture
def required_api_byom_realtime_custom():
    return [
        "pipeline_type",
        "model_name",
        "model_artifact_location",
        "inference_instance",
        "data_capture_location",
        "custom_image_uri",
    ]


@pytest.fixture
def required_api_byom_batch_custom():
    return [
        "pipeline_type",
        "custom_image_uri",
        "model_name",
        "model_artifact_location",
        "inference_instance",
        "batch_inference_data",
        "batch_job_output_location",
    ]


@pytest.fixture
def required_api_image_builder():
    return [
        "pipeline_type",
        "custom_algorithm_docker",
        "ecr_repo_name",
        "image_tag",
    ]


@pytest.fixture
def api_model_monitor_event():
    def _api_model_monitor_event(monitoring_type=""):
        monitor_event = {
            "pipeline_type": "byom_model_monitor",
            "model_name": "mymodel2",
            "endpoint_name": "xgb-churn-prediction-endpoint",
            "training_data": os.environ["TRAININGDATA"],
            "baseline_job_output_location": "bucket/baseline_job_output",
            "data_capture_location": os.environ["DATACAPTURE"],
            "monitoring_output_location": "bucket/monitoring_output",
            "schedule_expression": os.environ["SCHEDULEEXP"],
            "instance_type": os.environ["INSTANCETYPE"],
            "instance_volume_size": "20",
        }
        if monitoring_type.lower() != "" and monitoring_type.lower() in [
            "modelquality",
            "modelbias",
            "modelexplainability",
        ]:
            monitor_event["monitoring_type"] = monitoring_type.lower()
        return monitor_event

    return _api_model_monitor_event


@pytest.fixture
def required_api_keys_model_monitor():
    def _required_api_keys_model_monitor(monitoring_type, problem_type=None):
        common_keys = [
            "pipeline_type",
            "model_name",
            "endpoint_name",
            "baseline_data",
            "baseline_job_output_location",
            "data_capture_location",
            "monitoring_output_location",
            "schedule_expression",
            "monitor_max_runtime_seconds",
            "instance_type",
            "instance_volume_size",
        ]
        if monitoring_type != "ModelQuality":
            return common_keys
        else:
            common_model_keys = [
                "baseline_inference_attribute",
                "baseline_ground_truth_attribute",
                "problem_type",
                "monitor_ground_truth_input",
            ]
            if problem_type in ["Regression", "MulticlassClassification"]:
                common_model_keys.append("monitor_inference_attribute")

            # BinaryClassification problem
            else:
                common_model_keys.extend(
                    [
                        "monitor_probability_attribute",
                        "probability_threshold_attribute",
                        "baseline_probability_attribute",
                    ]
                )
            return [*common_keys, *common_model_keys]

    return _required_api_keys_model_monitor


@pytest.fixture
def template_parameters_common():
    def _template_parameters_common(event):
        template_parameters = [
            {
                "ParameterKey": "NOTIFICATIONEMAIL",
                "ParameterValue": os.environ["NOTIFICATION_EMAIL"],
                "UsePreviousValue": True,
            },
            {
                "ParameterKey": "BLUEPRINTBUCKET",
                "ParameterValue": os.environ["BLUEPRINT_BUCKET"],
                "UsePreviousValue": True,
            },
            {
                "ParameterKey": "ASSETSBUCKET",
                "ParameterValue": os.environ["ASSETS_BUCKET"],
                "UsePreviousValue": True,
            },
            {
                "ParameterKey": "MODELNAME",
                "ParameterValue": event["model_name"],
                "UsePreviousValue": True,
            },
            {
                "ParameterKey": "MODELARTIFACTLOCATION",
                "ParameterValue": event["model_artifact_location"],
                "UsePreviousValue": True,
            },
            {
                "ParameterKey": "INFERENCEINSTANCE",
                "ParameterValue": event["inference_instance"],
                "UsePreviousValue": True,
            },
        ]
        return template_parameters

    return _template_parameters_common


@pytest.fixture
def template_parameters_realtime_builtin(template_parameters_common):
    def _template_parameters_realtime_builtin(event):
        template_parameters = template_parameters_common(event)
        template_parameters.extend(
            [
                {
                    "ParameterKey": "MODELFRAMEWORK",
                    "ParameterValue": event["model_framework"],
                    "UsePreviousValue": True,
                },
                {
                    "ParameterKey": "MODELFRAMEWORKVERSION",
                    "ParameterValue": event["model_framework_version"],
                    "UsePreviousValue": True,
                },
            ]
        )

        return template_parameters

    return _template_parameters_realtime_builtin


@pytest.fixture
def template_parameters_batch_builtin(template_parameters_realtime_builtin):
    def _template_parameters_batch_builtin(event):
        template_parameters = template_parameters_realtime_builtin(event)
        template_parameters.extend(
            [
                {
                    "ParameterKey": "BATCHINFERENCEDATA",
                    "ParameterValue": event["batch_inference_data"],
                    "UsePreviousValue": True,
                },
            ]
        )

        return template_parameters

    return _template_parameters_batch_builtin


@pytest.fixture
def template_parameters_realtime_custom(template_parameters_common):
    def _template_parameters_realtime_custom(event):
        template_parameters = template_parameters_common(event)
        template_parameters.extend(
            [
                {
                    "ParameterKey": "CUSTOMCONTAINER",
                    "ParameterValue": event["custom_model_container"],
                    "UsePreviousValue": True,
                },
            ]
        )

        return template_parameters

    return _template_parameters_realtime_custom


@pytest.fixture
def template_parameters_batch_custom(template_parameters_realtime_custom):
    def _template_parameters_batch_custom(event):
        template_parameters = template_parameters_realtime_custom(event)
        template_parameters.extend(
            [
                {
                    "ParameterKey": "BATCHINFERENCEDATA",
                    "ParameterValue": event["batch_inference_data"],
                    "UsePreviousValue": True,
                },
            ]
        )

        return template_parameters

    return _template_parameters_batch_custom


@pytest.fixture
def generate_names():
    def _generate_names(endpoint_name, monitoring_type):
        baseline_job_name = f"{endpoint_name}-baseline-job-{str(uuid.uuid4())[:8]}"
        monitoring_schedule_name = f"{endpoint_name}-monitoring-schedule-{monitoring_type}-{str(uuid.uuid4())[:8]}"
        return (baseline_job_name, monitoring_schedule_name)

    return _generate_names


@pytest.fixture
def template_parameters_model_monitor(generate_names):
    def _template_parameters_model_monitor(event):
        baseline_job_name, monitoring_schedule_name = generate_names("test-endpoint", "dataquality")
        template_parameters = [
            {
                "ParameterKey": "NOTIFICATIONEMAIL",
                "ParameterValue": os.environ["NOTIFICATION_EMAIL"],
                "UsePreviousValue": True,
            },
            {
                "ParameterKey": "BLUEPRINTBUCKET",
                "ParameterValue": os.environ["BLUEPRINT_BUCKET"],
                "UsePreviousValue": True,
            },
            {
                "ParameterKey": "ASSETSBUCKET",
                "ParameterValue": os.environ["ASSETS_BUCKET"],
                "UsePreviousValue": True,
            },
            {
                "ParameterKey": "BASELINEJOBOUTPUTLOCATION",
                "ParameterValue": event.get("baseline_job_output_location"),
                "UsePreviousValue": True,
            },
            {
                "ParameterKey": "ENDPOINTNAME",
                "ParameterValue": event["endpoint_name"],
                "UsePreviousValue": True,
            },
            {
                "ParameterKey": "BASELINEJOBNAME",
                "ParameterValue": baseline_job_name,
                "UsePreviousValue": True,
            },
            {
                "ParameterKey": "MONITORINGSCHEDULENAME",
                "ParameterValue": monitoring_schedule_name,
                "UsePreviousValue": True,
            },
            {
                "ParameterKey": "MONITORINGOUTPUTLOCATION",
                "ParameterValue": event["monitoring_output_location"],
                "UsePreviousValue": True,
            },
            {
                "ParameterKey": "SCHEDULEEXPRESSION",
                "ParameterValue": event["schedule_expression"],
                "UsePreviousValue": True,
            },
            {
                "ParameterKey": "TRAININGDATA",
                "ParameterValue": event["training_data"],
                "UsePreviousValue": True,
            },
            {
                "ParameterKey": "INSTANCETYPE",
                "ParameterValue": event["instance_type"],
                "UsePreviousValue": True,
            },
            {
                "ParameterKey": "INSTANCEVOLUMESIZE",
                "ParameterValue": event["instance_volume_size"],
                "UsePreviousValue": True,
            },
            {
                "ParameterKey": "MONITORINGTYPE",
                "ParameterValue": event.get("monitoring_type", "dataquality"),
                "UsePreviousValue": True,
            },
            {
                "ParameterKey": "MAXRUNTIMESIZE",
                "ParameterValue": event.get("max_runtime_seconds", "-1"),
                "UsePreviousValue": True,
            },
        ]

        return template_parameters

    return _template_parameters_model_monitor


@pytest.fixture
def get_parameters_keys():
    def _get_parameters_keys(parameters):
        keys = [param["ParameterKey"] for param in parameters]
        return keys

    return _get_parameters_keys


@pytest.fixture
def cf_client_params(api_byom_event, template_parameters_realtime_builtin):
    template_parameters = template_parameters_realtime_builtin(api_byom_event("byom_realtime_builtin"))
    cf_params = {
        "Capabilities": ["CAPABILITY_IAM"],
        "OnFailure": "DO_NOTHING",
        "Parameters": template_parameters,
        "RoleARN": "arn:aws:role:region:account:action",
        "StackName": "teststack-testmodel-BYOMPipelineReatimeBuiltIn",
        "Tags": [{"Key": "stack_name", "Value": "teststack-testmodel-BYOMPipelineReatimeBuiltIn"}],
        "TemplateURL": "https://testurl/blueprints/byom/byom_realtime_builtin_container.yaml",
    }
    return cf_params


@pytest.fixture
def expected_update_response(stack_name):
    return {"StackId": f"Pipeline {stack_name} is already provisioned. No updates are to be performed."}