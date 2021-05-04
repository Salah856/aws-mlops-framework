# #####################################################################################################################
#  Copyright 2020-2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.                                       #
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
    aws_s3 as s3,
    aws_sns as sns,
    aws_sns_subscriptions as subscriptions,
    aws_events_targets as targets,
    aws_events as events,
    aws_codepipeline as codepipeline,
    core,
)
from lib.blueprints.byom.pipeline_definitions.source_actions import source_action_custom
from lib.blueprints.byom.pipeline_definitions.build_actions import build_action
from lib.blueprints.byom.pipeline_definitions.helpers import (
    pipeline_permissions,
    suppress_pipeline_bucket,
    suppress_iam_complex,
    suppress_sns,
)
from lib.blueprints.byom.pipeline_definitions.templates_parameters import (
    create_notification_email_parameter,
    create_assets_bucket_name_parameter,
    create_custom_container_parameter,
    create_ecr_repo_name_parameter,
    create_image_tag_parameter,
)


class BYOMCustomAlgorithmImageBuilderStack(core.Stack):
    def __init__(self, scope: core.Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # Parameteres #
        notification_email = create_notification_email_parameter(self)
        assets_bucket_name = create_assets_bucket_name_parameter(self)
        custom_container = create_custom_container_parameter(self)
        ecr_repo_name = create_ecr_repo_name_parameter(self)
        image_tag = create_image_tag_parameter(self)

        # Resources #
        assets_bucket = s3.Bucket.from_bucket_name(self, "AssetsBucket", assets_bucket_name.value_as_string)

        # Defining pipeline stages
        # source stage
        source_output, source_action_definition = source_action_custom(assets_bucket, custom_container)

        # build stage
        build_action_definition, container_uri = build_action(
            self, ecr_repo_name.value_as_string, image_tag.value_as_string, source_output
        )

        pipeline_notification_topic = sns.Topic(
            self,
            "PipelineNotification",
        )
        pipeline_notification_topic.node.default_child.cfn_options.metadata = suppress_sns()
        pipeline_notification_topic.add_subscription(
            subscriptions.EmailSubscription(email_address=notification_email.value_as_string)
        )

        # createing pipeline stages
        source_stage = codepipeline.StageProps(stage_name="Source", actions=[source_action_definition])
        build_stage = codepipeline.StageProps(stage_name="Build", actions=[build_action_definition])

        image_builder_pipeline = codepipeline.Pipeline(
            self,
            "BYOMPipelineReatimeBuild",
            stages=[source_stage, build_stage],
            cross_account_keys=False,
        )
        image_builder_pipeline.on_state_change(
            "NotifyUser",
            description="Notify user of the outcome of the pipeline",
            target=targets.SnsTopic(
                pipeline_notification_topic,
                message=events.RuleTargetInput.from_text(
                    (
                        f"Pipeline {events.EventField.from_path('$.detail.pipeline')} finished executing. "
                        f"Pipeline execution result is {events.EventField.from_path('$.detail.state')}"
                    )
                ),
            ),
            event_pattern=events.EventPattern(detail={"state": ["SUCCEEDED", "FAILED"]}),
        )

        image_builder_pipeline.add_to_role_policy(
            iam.PolicyStatement(
                actions=["events:PutEvents"],
                resources=[
                    f"arn:{core.Aws.PARTITION}:events:{core.Aws.REGION}:{core.Aws.ACCOUNT_ID}:event-bus/*",
                ],
            )
        )

        # add cfn nag supressions
        pipeline_child_nodes = image_builder_pipeline.node.find_all()
        pipeline_child_nodes[1].node.default_child.cfn_options.metadata = suppress_pipeline_bucket()
        pipeline_child_nodes[6].node.default_child.cfn_options.metadata = suppress_iam_complex()
        # attaching iam permissions to the pipelines
        pipeline_permissions(image_builder_pipeline, assets_bucket)

        # Outputs #
        core.CfnOutput(
            self,
            id="Pipelines",
            value=(
                f"https://console.aws.amazon.com/codesuite/codepipeline/pipelines/"
                f"{image_builder_pipeline.pipeline_name}/view?region={core.Aws.REGION}"
            ),
        )
        core.CfnOutput(
            self,
            id="CustomAlgorithmImageURI",
            value=container_uri,
        )