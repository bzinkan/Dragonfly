"""API layer: HTTP API Gateway + FastAPI Lambda.

Depends on DataStack (DynamoDB table, photo bucket) and AuthStack (user pool,
app client). Phase 0 exit criterion: `GET /health` returns 200 from this
stack's Lambda via the deployed API URL.
"""

from __future__ import annotations

from pathlib import Path

import aws_cdk as cdk
from aws_cdk import aws_apigatewayv2 as apigw
from aws_cdk import aws_apigatewayv2_authorizers as authorizers
from aws_cdk import aws_apigatewayv2_integrations as integrations
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_lambda as _lambda
from aws_cdk import aws_logs as logs
from aws_cdk import aws_s3 as s3
from constructs import Construct


class ApiStack(cdk.Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        env_name: str,
        table: dynamodb.Table,
        photo_bucket: s3.Bucket,
        user_pool: cognito.UserPool,
        app_client: cognito.UserPoolClient,
        **kwargs: object,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.api_fn = self._create_api_function(
            env_name, table, photo_bucket, user_pool, app_client
        )
        self.http_api = self._create_http_api(
            env_name, self.api_fn, user_pool, app_client
        )

        cdk.CfnOutput(
            self,
            "ApiUrl",
            value=self.http_api.api_endpoint,
            export_name=f"Dragonfly-ApiUrl-{env_name}",
        )

    def _create_api_function(
        self,
        env_name: str,
        table: dynamodb.Table,
        photo_bucket: s3.Bucket,
        user_pool: cognito.UserPool,
        app_client: cognito.UserPoolClient,
    ) -> _lambda.Function:
        backend_dir = Path(__file__).resolve().parents[2] / "backend"

        fn = _lambda.Function(
            self,
            "ApiFunction",
            function_name=f"Dragonfly-Api-{env_name}",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="app.main.handler",
            code=_lambda.Code.from_asset(
                str(backend_dir),
                bundling=cdk.BundlingOptions(
                    image=_lambda.Runtime.PYTHON_3_12.bundling_image,
                    command=[
                        "bash",
                        "-c",
                        # Use uv to export a requirements file, then pip-install
                        # into /asset-output and copy the app package alongside.
                        "pip install uv && "
                        "uv export --format requirements-txt --no-dev --no-hashes "
                        "> /tmp/requirements.txt && "
                        "pip install -r /tmp/requirements.txt -t /asset-output && "
                        "cp -r app /asset-output/",
                    ],
                ),
            ),
            memory_size=512,
            timeout=cdk.Duration.seconds(29),  # API Gateway integration max
            architecture=_lambda.Architecture.ARM_64,
            environment={
                "DRAGONFLY_ENV": env_name,
                "DRAGONFLY_TABLE_NAME": table.table_name,
                "DRAGONFLY_S3_BUCKET": photo_bucket.bucket_name,
                "DRAGONFLY_COGNITO_USER_POOL_ID": user_pool.user_pool_id,
                "DRAGONFLY_COGNITO_APP_CLIENT_ID": app_client.user_pool_client_id,
                # Secrets (iNat project credentials, Rekognition thresholds)
                # are loaded from SSM Parameter Store at cold start. Never
                # inject secrets via Lambda environment variables, even in dev.
                # See docs/architecture.md § Deployment.
            },
            log_retention=logs.RetentionDays.ONE_MONTH,
            tracing=_lambda.Tracing.ACTIVE,
        )

        table.grant_read_write_data(fn)
        photo_bucket.grant_read_write(fn)

        # Cognito admin actions for the kid-provisioning flow (parent/teacher
        # creates a kid account from inside the app).
        user_pool.grant(
            fn,
            "cognito-idp:AdminCreateUser",
            "cognito-idp:AdminSetUserPassword",
            "cognito-idp:AdminUpdateUserAttributes",
            "cognito-idp:AdminGetUser",
        )

        return fn

    def _create_http_api(
        self,
        env_name: str,
        fn: _lambda.Function,
        user_pool: cognito.UserPool,
        app_client: cognito.UserPoolClient,
    ) -> apigw.HttpApi:
        jwt_authorizer = authorizers.HttpJwtAuthorizer(
            "CognitoAuthorizer",
            jwt_issuer=(
                f"https://cognito-idp.{self.region}.amazonaws.com/"
                f"{user_pool.user_pool_id}"
            ),
            jwt_audience=[app_client.user_pool_client_id],
        )

        http_api = apigw.HttpApi(
            self,
            "DragonflyHttpApi",
            api_name=f"Dragonfly-{env_name}",
            default_authorizer=jwt_authorizer,
            cors_preflight=apigw.CorsPreflightOptions(
                # Tightened in prod via a follow-up — for Phase 0/1 the Expo web
                # dev server and staging origins are both needed.
                allow_origins=["*"],
                allow_methods=[apigw.CorsHttpMethod.ANY],
                allow_headers=["authorization", "content-type"],
                max_age=cdk.Duration.hours(1),
            ),
        )

        integration = integrations.HttpLambdaIntegration(
            "ApiIntegration", fn
        )

        # /health is the Phase 0 exit criterion — explicitly unauthenticated
        # so the Expo app can hit it before login is wired up.
        http_api.add_routes(
            path="/health",
            methods=[apigw.HttpMethod.GET],
            integration=integration,
            authorizer=authorizers.HttpNoneAuthorizer(),
        )

        # Versioned, authenticated API surface — everything else.
        http_api.add_routes(
            path="/v1/{proxy+}",
            methods=[apigw.HttpMethod.ANY],
            integration=integration,
        )

        return http_api
