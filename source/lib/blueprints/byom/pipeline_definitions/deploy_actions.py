# #####################################################################################################################
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
from aws_cdk import (
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_codepipeline_actions as codepipeline_actions,
    aws_cloudformation as cloudformation,
    core,
)
from lib.blueprints.byom.pipeline_definitions.helpers import (
    suppress_lambda_policies,
    suppress_pipeline_policy,
    add_logs_policy,
)
from lib.conditional_resource import ConditionalResources
from lib.blueprints.byom.pipeline_definitions.cdk_context_value import get_cdk_context_value
from lib.blueprints.byom.pipeline_definitions.iam_policies import (
    create_service_role,
    sagemaker_baseline_job_policy,
    sagemaker_logs_metrics_policy_document,
    batch_transform_policy,
    s3_policy_write,
    s3_policy_read,
    cloudformation_stackset_policy,
    cloudformation_stackset_instances_policy,
    kms_policy_document,
    delegated_admin_policy_document,
)


lambda_service = "lambda.amazonaws.com"
lambda_handler = "main.handler"


def sagemaker_layer(scope, blueprint_bucket):
    """
    sagemaker_layer creates a Lambda layer with Sagemaker SDK installed in it to allow Lambda functions call
    Sagemaker SDK's methods such as create_model(), etc.

    :blueprint_bucket: CDK object of the blueprint bucket that contains resources for BYOM pipeline
    :scope: CDK Construct scope that's needed to create CDK resources
    :return: Lambda layer version in a form of a CDK object
    """
    # Lambda sagemaker layer for sagemaker sdk that is used in create sagemaker model step
    return lambda_.LayerVersion(
        scope,
        "sagemakerlayer",
        code=lambda_.Code.from_bucket(blueprint_bucket, "blueprints/byom/lambdas/sagemaker_layer.zip"),
        compatible_runtimes=[lambda_.Runtime.PYTHON_3_8],
    )


def batch_transform(
    scope,  # NOSONAR:S107 this function is designed to take many arguments
    id,
    blueprint_bucket,
    assets_bucket,
    model_name,
    inference_instance,
    batch_input_bucket,
    batch_inference_data,
    batch_job_output_location,
    kms_key_arn,
    sm_layer,
):
    """
    batch_transform creates a sagemaker batch transform job in a lambda

    :scope: CDK Construct scope that's needed to create CDK resources
    :blueprint_bucket: CDK object of the blueprint bucket that contains resources for BYOM pipeline
    :assets_bucket: the bucket cdk object where pipeline assets are stored
    :model_name: name of the sagemaker model to be created, in the form of a CDK CfnParameter object
    :inference_instance: compute instance type for the sagemaker inference endpoint, in the form of
    a CDK CfnParameter object
    :batch_input_bucket: bucket name where the batch data is stored
    :batch_inference_data: location of the batch inference data in assets bucket, in the form of
    a CDK CfnParameter object
    :batch_job_output_location: S3 bucket location where the result of the batch job will be stored
    :kms_key_arn: optional kmsKeyArn used to encrypt job's output and instance volume.
    :sm_layer: sagemaker lambda layer
    :return: Lambda function
    """
    s3_read = s3_policy_read(
        list(
            set(
                [
                    f"arn:aws:s3:::{assets_bucket.bucket_name}",
                    f"arn:aws:s3:::{assets_bucket.bucket_name}/*",
                    f"arn:aws:s3:::{batch_input_bucket}",
                    f"arn:aws:s3:::{batch_inference_data}",
                ]
            )
        )
    )
    s3_write = s3_policy_write(
        [
            f"arn:aws:s3:::{batch_job_output_location}/*",
        ]
    )

    batch_transform_permissions = batch_transform_policy()

    lambda_role = create_service_role(
        scope,
        "batch_transform_lambda_role",
        "lambda.amazonaws.com",
        (
            "Role that creates a lambda function assumes to create a sagemaker batch transform "
            "job in the aws mlops pipeline."
        ),
    )

    lambda_role.add_to_policy(batch_transform_permissions)
    lambda_role.add_to_policy(s3_read)
    lambda_role.add_to_policy(s3_write)
    add_logs_policy(lambda_role)

    batch_transform_lambda = lambda_.Function(
        scope,
        id,
        runtime=lambda_.Runtime.PYTHON_3_8,
        handler="main.handler",
        layers=[sm_layer],
        role=lambda_role,
        code=lambda_.Code.from_bucket(blueprint_bucket, "blueprints/byom/lambdas/batch_transform.zip"),
        environment={
            "model_name": model_name,
            "inference_instance": inference_instance,
            "assets_bucket": assets_bucket.bucket_name,
            "batch_inference_data": batch_inference_data,
            "batch_job_output_location": batch_job_output_location,
            "kms_key_arn": kms_key_arn,
            "LOG_LEVEL": "INFO",
        },
    )

    batch_transform_lambda.node.default_child.cfn_options.metadata = suppress_lambda_policies()

    return batch_transform_lambda


def create_baseline_job_lambda(
    scope,  # NOSONAR:S107 this function is designed to take many arguments
    blueprint_bucket,
    assets_bucket,
    monitoring_type,
    baseline_job_name,
    baseline_data_location,
    baseline_job_output_location,
    endpoint_name,
    instance_type,
    instance_volume_size,
    max_runtime_seconds,
    kms_key_arn,
    kms_key_arn_provided_condition,
    stack_name,
    sm_layer,
    problem_type=None,
    ground_truth_attribute=None,
    inference_attribute=None,
    probability_attribute=None,
    probability_threshold_attribute=None,
):
    """
    create_baseline_job_lambda creates a data/model baseline processing job in a lambda invoked codepipeline action

    :scope: CDK Construct scope that's needed to create CDK resources
    :blueprint_bucket: CDK object of the blueprint bucket that contains resources for BYOM pipeline
    :assets_bucket: the bucket cdk object where pipeline assets are stored
    :monitoring_type: SageMaker's monitoring type. Currently supported types (DataQualit/ModelQuality)
    :baseline_job_name: name of the baseline job to be created
    :baseline_data_location: location of the baseline data to create the SageMaker Model Monitor baseline
    :baseline_job_output_location: S3 prefix in the S3 assets bucket to store the output of the job
    :endpoint_name: name of the deployed SageMaker endpoint to be monitored
    :instance_type: compute instance type for the baseline job, in the form of a CDK CfnParameter object
    :instance_volume_size: volume size of the EC2 instance
    :max_runtime_seconds: max time the job is allowed to run
    :kms_key_arn: kms key arn to encrypt the baseline job's output
    :stack_name: model monitor stack name
    :sm_layer: sagemaker lambda layer
    :problem_type: used with ModelQuality baseline. Type of Machine Learning problem. Valid values are
            ['Regression'|'BinaryClassification'|'MulticlassClassification'] (default: None)
    :ground_truth_attribute: index or JSONpath to locate actual label(s) (used with ModelQuality baseline).
            (default: None).
    :inference_attribute: index or JSONpath to locate predicted label(s) (used with ModelQuality baseline).
        Required for 'Regression'|'MulticlassClassification' problems,
        and not required for 'BinaryClassification' if 'probability_attribute' and
        'probability_threshold_attribute' are provided (default: None).
    :probability_attribute: index or JSONpath to locate probabilities(used with ModelQuality baseline).
        Used only with 'BinaryClassification' problem if 'inference_attribute' is not provided (default: None).
    :probability_threshold_attribute: threshold to convert probabilities to binaries (used with ModelQuality baseline).
        Used only with 'BinaryClassification' problem if 'inference_attribute' is not provided (default: None).
    :return: codepipeline action in a form of a CDK object that can be attached to a codepipeline stage
    """
    s3_read = s3_policy_read(
        [
            f"arn:aws:s3:::{assets_bucket.bucket_name}",
            f"arn:aws:s3:::{assets_bucket.bucket_name}/{baseline_data_location}",
        ]
    )
    s3_write = s3_policy_write(
        [
            f"arn:aws:s3:::{baseline_job_output_location}/*",
        ]
    )

    create_baseline_job_policy = sagemaker_baseline_job_policy(baseline_job_name)
    sagemaker_logs_policy = sagemaker_logs_metrics_policy_document(scope, "BaselineLogsMetrics")

    # Kms Key permissions
    kms_policy = kms_policy_document(scope, "BaselineKmsPolicy", kms_key_arn)
    # add conditions to KMS and ECR policies
    core.Aspects.of(kms_policy).add(ConditionalResources(kms_key_arn_provided_condition))

    # create sagemaker role
    sagemaker_role = create_service_role(
        scope,
        "create_baseline_sagemaker_role",
        "sagemaker.amazonaws.com",
        "Role that is create sagemaker model Lambda function assumes to create a baseline job.",
    )
    # attach the conditional policies
    kms_policy.attach_to_role(sagemaker_role)

    # create a trust relation to assume the Role
    sagemaker_role.add_to_policy(iam.PolicyStatement(actions=["sts:AssumeRole"], resources=[sagemaker_role.role_arn]))
    # creating a role so that this lambda can create a baseline job
    lambda_role = create_service_role(
        scope,
        "create_baseline_job_lambda_role",
        lambda_service,
        "Role that is create_data_baseline_job Lambda function assumes to create a baseline job in the pipeline.",
    )

    sagemaker_logs_policy.attach_to_role(sagemaker_role)
    sagemaker_role.add_to_policy(create_baseline_job_policy)
    sagemaker_role.add_to_policy(s3_read)
    sagemaker_role.add_to_policy(s3_write)
    sagemaker_role_nodes = sagemaker_role.node.find_all()
    sagemaker_role_nodes[2].node.default_child.cfn_options.metadata = suppress_pipeline_policy()
    lambda_role.add_to_policy(iam.PolicyStatement(actions=["iam:PassRole"], resources=[sagemaker_role.role_arn]))
    lambda_role.add_to_policy(create_baseline_job_policy)
    lambda_role.add_to_policy(s3_write)
    lambda_role.add_to_policy(s3_read)
    add_logs_policy(lambda_role)

    # defining the lambda function that gets invoked in this stage
    # create environment variabes
    lambda_environment_variables = {
        "MONITORING_TYPE": monitoring_type,
        "BASELINE_JOB_NAME": baseline_job_name,
        "ASSETS_BUCKET": assets_bucket.bucket_name,
        "SAGEMAKER_ENDPOINT_NAME": endpoint_name,
        "BASELINE_DATA_LOCATION": baseline_data_location,
        "BASELINE_JOB_OUTPUT_LOCATION": baseline_job_output_location,
        "INSTANCE_TYPE": instance_type,
        "INSTANCE_VOLUME_SIZE": instance_volume_size,
        "MAX_RUNTIME_SECONDS": max_runtime_seconds,
        "ROLE_ARN": sagemaker_role.role_arn,
        "KMS_KEY_ARN": kms_key_arn,
        "STACK_NAME": stack_name,
        "LOG_LEVEL": "INFO",
    }

    # add ModelQuality related variables (they will be passed by the Model Monitor stack)
    if monitoring_type == "ModelQuality":
        lambda_environment_variables.update(
            {
                "PROBLEM_TYPE": problem_type,
                "GROUND_TRUTH_ATTRIBUTE": ground_truth_attribute,
                "INFERENCE_ATTRIBUTE": inference_attribute,
                "PROBABILITY_ATTRIBUTE": probability_attribute,
                "PROBABILITY_THRESHOLD_ATTRIBUTE": probability_threshold_attribute,
            }
        )
    create_baseline_job_lambda = lambda_.Function(
        scope,
        "create_data_baseline_job",
        runtime=lambda_.Runtime.PYTHON_3_8,
        handler=lambda_handler,
        role=lambda_role,
        code=lambda_.Code.from_bucket(blueprint_bucket, "blueprints/byom/lambdas/create_baseline_job.zip"),
        layers=[sm_layer],
        environment=lambda_environment_variables,
        timeout=core.Duration.minutes(10),
    )

    create_baseline_job_lambda.node.default_child.cfn_options.metadata = suppress_lambda_policies()
    role_child_nodes = create_baseline_job_lambda.role.node.find_all()
    role_child_nodes[2].node.default_child.cfn_options.metadata = suppress_pipeline_policy()

    return create_baseline_job_lambda


def create_stackset_action(
    scope,  # NOSONAR:S107 this function is designed to take many arguments
    action_name,
    blueprint_bucket,
    source_output,
    artifact,
    template_file,
    stage_params_file,
    account_ids,
    org_ids,
    regions,
    assets_bucket,
    stack_name,
    delegated_admin_condition,
):
    """
    create_stackset_action an invokeLambda action to be added to AWS Codepipeline stage

    :scope: CDK Construct scope that's needed to create CDK resources
    :action_name: name of the StackSet action
    :blueprint_bucket: CDK object of the blueprint bucket that contains resources for BYOM pipeline
    :source_output: CDK object of the Source action's output
    :artifact: name of the input artifact to the StackSet action
    :template_file: name of the Cloudformation template to be deployed
    :stage_params_file: name of the template parameters for the stage
    :account_ids: list of AWS accounts where the stack with be deployed
    :org_ids: list of AWS organizational ids where the stack with be deployed
    :regions: list of regions where the stack with be deployed
    :assets_bucket: the bucket cdk object where pipeline assets are stored
    :stack_name: name of the stack to be deployed
    :delegated_admin_condition: CDK condition to indicate if a delegated admin account is used
    :return: codepipeline invokeLambda action in a form of a CDK object that can be attached to a codepipeline stage
    """
    # creating a role so that this lambda can create a baseline job
    lambda_role = create_service_role(
        scope,
        f"{action_name}_role",
        lambda_service,
        "The role that is assumed by create_update_cf_stackset Lambda function.",
    )

    # cloudformation stackset permissions
    # get the account_id based on whether a delegated admin account or management account is used
    account_id = core.Fn.condition_if(
        delegated_admin_condition.logical_id,
        "*",  # used when a delegated admin account is used (i.e., the management account_id is not known)
        core.Aws.ACCOUNT_ID,  # used when the management account is used
    ).to_string()
    cloudformation_stackset_permissions = cloudformation_stackset_policy(stack_name, account_id)
    cloudformation_stackset_instances_permissions = cloudformation_stackset_instances_policy(stack_name, account_id)

    lambda_role.add_to_policy(cloudformation_stackset_permissions)
    lambda_role.add_to_policy(cloudformation_stackset_instances_permissions)
    add_logs_policy(lambda_role)

    # add delegated admin account policy
    delegated_admin_policy = delegated_admin_policy_document(scope, f"{action_name}DelegatedAdminPolicy")
    # create only if a delegated admin account is used
    core.Aspects.of(delegated_admin_policy).add(ConditionalResources(delegated_admin_condition))
    # attached the policy to the role
    delegated_admin_policy.attach_to_role(lambda_role)

    # defining the lambda function that gets invoked in this stage
    create_update_cf_stackset_lambda = lambda_.Function(
        scope,
        f"{action_name}_stackset_lambda",
        runtime=lambda_.Runtime.PYTHON_3_8,
        handler="main.lambda_handler",
        role=lambda_role,
        code=lambda_.Code.from_bucket(blueprint_bucket, "blueprints/byom/lambdas/create_update_cf_stackset.zip"),
        timeout=core.Duration.minutes(15),
        # setup the CallAS for CF StackSet
        environment={
            "CALL_AS": core.Fn.condition_if(delegated_admin_condition.logical_id, "DELEGATED_ADMIN", "SELF").to_string()
        },
    )

    create_update_cf_stackset_lambda.node.default_child.cfn_options.metadata = suppress_lambda_policies()
    role_child_nodes = create_update_cf_stackset_lambda.role.node.find_all()
    role_child_nodes[2].node.default_child.cfn_options.metadata = suppress_pipeline_policy()

    # Create codepipeline action
    create_stackset_action = codepipeline_actions.LambdaInvokeAction(
        action_name=action_name,
        inputs=[source_output],
        variables_namespace=f"{action_name}-namespace",
        lambda_=create_update_cf_stackset_lambda,
        user_parameters={
            "stackset_name": stack_name,
            "artifact": artifact,
            "template_file": template_file,
            "stage_params_file": stage_params_file,
            "account_ids": account_ids,
            "org_ids": org_ids,
            "regions": regions,
        },
        run_order=1,
    )
    return (create_update_cf_stackset_lambda.function_arn, create_stackset_action)


def create_cloudformation_action(
    scope, action_name, stack_name, source_output, template_file, template_parameters_file, run_order=1
):
    """
    create_cloudformation_action a CloudFormation action to be added to AWS Codepipeline stage

    :scope: CDK Construct scope that's needed to create CDK resources
    :action_name: name of the StackSet action
    :stack_name: name of the stack to be deployed
    :source_output: CDK object of the Source action's output
    :template_file: name of the Cloudformation template to be deployed
    :template_parameters_file: name of the template parameters
    :return: codepipeline CloudFormation action in a form of a CDK object that can be attached to a codepipeline stage
    """

    # Create codepipeline's cloudformation action
    create_cloudformation_action = codepipeline_actions.CloudFormationCreateUpdateStackAction(
        action_name=action_name,
        stack_name=stack_name,
        capabilities=[cloudformation.CloudFormationCapabilities.NAMED_IAM],
        template_path=source_output.at_path(template_file),
        # Admin permissions are added to the deployment role used by the CF action for simplicity
        # and deploy different resources by different MLOps pipelines. Roles are defined by the
        # pipelines' cloudformation templates.
        admin_permissions=True,
        template_configuration=source_output.at_path(template_parameters_file),
        variables_namespace=f"{action_name}-namespace",
        replace_on_failure=True,
        run_order=run_order,
    )

    return create_cloudformation_action


def create_invoke_lambda_custom_resource(
    scope,  # NOSONAR:S107 this function is designed to take many arguments
    id,
    lambda_function_arn,
    lambda_function_name,
    blueprint_bucket,
    custom_resource_properties,
):
    """
    create_invoke_lambda_custom_resource creates a custom resource to invoke lambda function

    :scope: CDK Construct scope that's needed to create CDK resources
    :id: the logicalId of teh CDK resource
    :lambda_function_arn: arn of the lambda function to be invoked (str)
    :lambda_function_name: name of the lambda function to be invoked (str)
    :blueprint_bucket: CDK object of the blueprint bucket that contains resources for BYOM pipeline
    :custom_resource_properties: user provided properties (dict)

    :return: CDK Custom Resource
    """
    custom_resource_lambda_fn = lambda_.Function(
        scope,
        id,
        code=lambda_.Code.from_bucket(blueprint_bucket, "blueprints/byom/lambdas/invoke_lambda_custom_resource.zip"),
        handler="index.handler",
        runtime=lambda_.Runtime.PYTHON_3_8,
        timeout=core.Duration.minutes(5),
    )

    custom_resource_lambda_fn.add_to_role_policy(
        iam.PolicyStatement(
            actions=[
                "lambda:InvokeFunction",
            ],
            resources=[lambda_function_arn],
        )
    )
    custom_resource_lambda_fn.node.default_child.cfn_options.metadata = suppress_lambda_policies()

    invoke_lambda_custom_resource = core.CustomResource(
        scope,
        f"{id}CustomResource",
        service_token=custom_resource_lambda_fn.function_arn,
        properties={
            "function_name": lambda_function_name,
            "message": f"Invoking lambda function: {lambda_function_name}",
            **custom_resource_properties,
        },
        resource_type="Custom::InvokeLambda",
    )

    return invoke_lambda_custom_resource


def create_copy_assets_lambda(scope, blueprint_repository_bucket_name):
    """
    create_copy_assets_lambda creates the custom resource's lambda function to copy assets to s3

    :scope: CDK Construct scope that's needed to create CDK resources
    :blueprint_repository_bucket_name: name of the blueprint S3 bucket

    :return: CDK Lambda Function
    """
    # if you're building the solution locally, replace source_bucket and file_key with your values
    source_bucket = f"{get_cdk_context_value(scope, 'SourceBucket')}-{core.Aws.REGION}"
    file_key = (
        f"{get_cdk_context_value(scope,'SolutionName')}/{get_cdk_context_value(scope,'Version')}/"
        f"{get_cdk_context_value(scope,'BlueprintsFile')}"
    )

    custom_resource_lambda_fn = lambda_.Function(
        scope,
        "CustomResourceLambda",
        code=lambda_.Code.from_asset("lambdas/custom_resource"),
        handler="index.on_event",
        runtime=lambda_.Runtime.PYTHON_3_8,
        memory_size=256,
        environment={
            "SOURCE_BUCKET": source_bucket,
            "FILE_KEY": file_key,
            "DESTINATION_BUCKET": blueprint_repository_bucket_name,
            "LOG_LEVEL": "INFO",
        },
        timeout=core.Duration.minutes(10),
    )

    custom_resource_lambda_fn.node.default_child.cfn_options.metadata = suppress_lambda_policies()
    # grant permission to download the file from the source bucket
    custom_resource_lambda_fn.add_to_role_policy(
        s3_policy_read([f"arn:aws:s3:::{source_bucket}", f"arn:aws:s3:::{source_bucket}/*"])
    )

    return custom_resource_lambda_fn


def create_solution_helper(scope):
    """
    create_solution_helper creates the solution helper lambda function

    :scope: CDK Construct scope that's needed to create CDK resources

    :return: CDK Lambda Function
    """
    helper_function = lambda_.Function(
        scope,
        "SolutionHelper",
        code=lambda_.Code.from_asset("lambdas/solution_helper"),
        handler="lambda_function.handler",
        runtime=lambda_.Runtime.PYTHON_3_8,
        timeout=core.Duration.minutes(5),
    )

    helper_function.node.default_child.cfn_options.metadata = suppress_lambda_policies()

    return helper_function


def create_uuid_custom_resource(scope, create_model_registry, helper_function_arn):
    """
    create_uuid_custom_resource creates the CreateUUID Custom Resource

    :scope: CDK Construct scope that's needed to create CDK resources
    :create_model_registry: whether or not the solution will create a SageMaker Model registry (Yes/No)
    :helper_function_arn: solution helper lambda function arn

    :return: CDK Custom Resource
    """
    return core.CustomResource(
        scope,
        "CreateUniqueID",
        service_token=helper_function_arn,
        # add the template's paramater "create_model_registry" to the custom resource properties
        # so that a new UUID is generated when this value is updated
        # the generated UUID is appended to the name of the model registry to be created
        properties={"Resource": "UUID", "CreateModelRegistry": create_model_registry},
        resource_type="Custom::CreateUUID",
    )


def create_send_data_custom_resource(scope, helper_function_arn, properties):
    """
    create_send_data_custom_resource creates AnonymousData Custom Resource

    :scope: CDK Construct scope that's needed to create CDK resources
    :helper_function_arn: solution helper lambda function arn
    :properties: Custom Resource properties

    :return: CDK Custom Resource
    """
    return core.CustomResource(
        scope,
        "SendAnonymousData",
        service_token=helper_function_arn,
        properties=properties,
        resource_type="Custom::AnonymousData",
    )
