# #####################################################################################################################
#  Copyright 2020 Amazon.com, Inc. or its affiliates. All Rights Reserved.                                            #
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
from aws_cdk import aws_iam as iam, core


def pipeline_permissions(pipeline, assets_bucket):
    """
    pipeline_permissions adds necessary permissions for a codepipeline to operate. A helper function to attach
    permissions to different types of pipeline created based on user parameters.

    :pipeline: Codepipeilne instsance in a form of a CDK object
    :assets_bucket: the bucket cdk object where pipeline assets are stored
    :return: nothing
    """
    pipeline.add_to_role_policy(
        iam.PolicyStatement(
            actions=[
                "s3:GetObject",
                "lambda:GetFunctionConfiguration",
                "logs:DescribeLogGroups",
            ],
            resources=[
                assets_bucket.arn_for_objects("*"),
                "arn:" + core.Aws.PARTITION + ":lambda:" + core.Aws.REGION + ":" + core.Aws.ACCOUNT_ID + ":function:*",
                "arn:" + core.Aws.PARTITION + ":logs:" + core.Aws.REGION + ":" + core.Aws.ACCOUNT_ID + ":log-group:*",
            ],
        )
    )


def codepipeline_policy():
    """
    codepipeline_policy creates IAM policy statement that grants codepipeline interaction from a lambda function
    that is invoked by codepipeline actions.

    :return: iam policy statement with PutJobSuccessResult and PutJobFailureResult permissions for CodePipeline
    """
    return iam.PolicyStatement(
        actions=[
            "codepipeline:PutJobSuccessResult",
            "codepipeline:PutJobFailureResult",
        ],
        # IAM doesn't support PutJobSuccessResult and PutJobFailureResult actions to be bound to resources
        resources=["*"],
    )


def add_logs_policy(function_role):
    function_role.add_to_policy(
        iam.PolicyStatement(
            actions=[
                "logs:CreateLogStream",
                "logs:PutLogEvents",
            ],
            resources=[
                "arn:"
                + core.Aws.PARTITION
                + ":logs:"
                + core.Aws.REGION
                + ":"
                + core.Aws.ACCOUNT_ID
                + ":log-group:/aws/lambda/*",
                "arn:"
                + core.Aws.PARTITION
                + ":logs:"
                + core.Aws.REGION
                + ":"
                + core.Aws.ACCOUNT_ID
                + ":log-group:*:log-stream:*",
            ],
        )
    )
    function_role.add_to_policy(
        iam.PolicyStatement(
            actions=["logs:CreateLogGroup"],
            resources=["arn:" + core.Aws.PARTITION + ":logs:" + core.Aws.REGION + ":" + core.Aws.ACCOUNT_ID + ":*"],
        )
    )


def suppress_cloudwatch_policy():
    return {
        "cfn_nag": {
            "rules_to_suppress": [
                {
                    "id": "W58",
                    "reason": "The lambda functions role already has permissions to write cloudwatch logs",
                }
            ]
        }
    }


def suppress_pipeline_policy():
    return {
        "cfn_nag": {
            "rules_to_suppress": [
                {
                    "id": "W12",
                    "reason": (
                        "The codepipeline permissions PutJobSuccessResult and PutJobFailureResult "
                        "are not able to be bound to resources."
                    ),
                }
            ]
        }
    }


def suppress_list_function_policy():
    return {
        "cfn_nag": {
            "rules_to_suppress": [
                {
                    "id": "W12",
                    "reason": "The lambda permission ListFunctions is not able to be bound to resources.",
                }
            ]
        }
    }


def suppress_s3_access_policy():
    return {
        "cfn_nag": {
            "rules_to_suppress": [
                {"id": "W35", "reason": "This is the access bucket"},
            ]
        }
    }


def suppress_assets_bucket():
    return {
        "cfn_nag": {
            "rules_to_suppress": [
                {
                    "id": "W51",
                    "reason": (
                        "This bucket does not need bucket policy. Permissions write to this bucket are set with IAM."
                    ),
                }
            ]
        }
    }


def suppress_pipeline_bucket():
    return {
        "cfn_nag": {
            "rules_to_suppress": [
                {
                    "id": "W51",
                    "reason": (
                        "This bucket does not need bucket policy. Permissions write to this bucket are set with IAM."
                    ),
                },
                {
                    "id": "W35",
                    "reason": (
                        "This bucket is auto generated by CDK's codepipeline construct to handle its assets."
                        " It does not need access logging"
                    ),
                },
            ]
        }
    }


def suppress_iam_complex():
    return {
        "cfn_nag": {
            "rules_to_suppress": [
                {
                    "id": "W76",
                    "reason": "Complex iam policy is required for this functionality",
                }
            ]
        }
    }


def suppress_sns():
    return {
        "cfn_nag": {
            "rules_to_suppress": [
                {
                    "id": "W47",
                    "reason": "This SNS topic does not contain any sensitive information.",
                }
            ]
        }
    }


def suppress_ecr_policy():
    return {
        "cfn_nag": {
            "rules_to_suppress": [
                {
                    "id": "W12",
                    "reason": "This ECR Policy (ecr:GetAuthorizationToken) can not have a restricted resource.",
                }
            ]
        }
    }


def apply_secure_bucket_policy(bucket):
    bucket.add_to_resource_policy(
        iam.PolicyStatement(
            sid="HttpsOnly",
            effect=iam.Effect.DENY,
            actions=["*"],
            resources=[f"{bucket.bucket_arn}/*"],
            principals=[iam.AnyPrincipal()],
            conditions={"Bool": {"aws:SecureTransport": "false"}},
        )
    )
