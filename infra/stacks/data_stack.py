"""Data layer: DynamoDB table + S3 photo bucket.

The keys here must stay in lockstep with docs/data-model.md.
If you change them, update the doc in the same PR.
"""

from __future__ import annotations

import aws_cdk as cdk
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_s3 as s3
from constructs import Construct


class DataStack(cdk.Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        env_name: str,
        **kwargs: object,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.table = self._create_table(env_name)
        self.photo_bucket = self._create_photo_bucket(env_name)

        # Outputs — imported by ApiStack and WorkersStack.
        cdk.CfnOutput(
            self,
            "TableName",
            value=self.table.table_name,
            export_name=f"Dragonfly-TableName-{env_name}",
        )
        cdk.CfnOutput(
            self,
            "PhotoBucketName",
            value=self.photo_bucket.bucket_name,
            export_name=f"Dragonfly-PhotoBucket-{env_name}",
        )

    def _create_table(self, env_name: str) -> dynamodb.Table:
        """The one table. Single-table design; see docs/data-model.md."""
        table = dynamodb.Table(
            self,
            "DragonflyTable",
            table_name=f"Dragonfly-{env_name}",
            partition_key=dynamodb.Attribute(
                name="PK", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="SK", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=env_name != "dev",
            ),
            removal_policy=(
                cdk.RemovalPolicy.DESTROY
                if env_name == "dev"
                else cdk.RemovalPolicy.RETAIN
            ),
            encryption=dynamodb.TableEncryption.AWS_MANAGED,
        )

        # GSI1 — alternate lookups: email→user, joinCode→group,
        # user→groups, groupId→observations-over-time, status→review queue
        table.add_global_secondary_index(
            index_name="GSI1",
            partition_key=dynamodb.Attribute(
                name="GSI1PK", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="GSI1SK", type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # GSI2 — species-wide access: "who else found this taxon?"
        # Sparse: only observation rows populate GSI2PK/GSI2SK.
        table.add_global_secondary_index(
            index_name="GSI2",
            partition_key=dynamodb.Attribute(
                name="GSI2PK", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="GSI2SK", type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        return table

    def _create_photo_bucket(self, env_name: str) -> s3.Bucket:
        """Observation photos. Uploads land in pending/, moderation promotes
        to observations/ or moves to quarantine/.
        """
        bucket = s3.Bucket(
            self,
            "PhotoBucket",
            bucket_name=f"dragonfly-photos-{env_name}-{self.account}",
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            versioned=env_name == "prod",
            removal_policy=(
                cdk.RemovalPolicy.DESTROY
                if env_name == "dev"
                else cdk.RemovalPolicy.RETAIN
            ),
            auto_delete_objects=env_name == "dev",
            cors=[
                s3.CorsRule(
                    allowed_methods=[s3.HttpMethods.PUT, s3.HttpMethods.GET],
                    allowed_origins=["*"],  # tightened in ApiStack for prod
                    allowed_headers=["*"],
                    max_age=3000,
                )
            ],
            lifecycle_rules=[
                # Anything still in pending/ after 24h was abandoned.
                s3.LifecycleRule(
                    id="expire-pending",
                    prefix="pending/",
                    expiration=cdk.Duration.days(1),
                ),
                # Quarantined photos kept 30 days for teacher review,
                # then deleted.
                s3.LifecycleRule(
                    id="expire-quarantine",
                    prefix="quarantine/",
                    expiration=cdk.Duration.days(30),
                ),
            ],
        )
        return bucket
