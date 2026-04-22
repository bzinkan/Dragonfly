"""Auth layer: Cognito user pool for Dragonfly.

Custom attributes (`custom:role`, `custom:group_id`) are checked by the
API's JWT dependency. See `docs/architecture.md` for the auth model.

Kids under 13 do not have email addresses. They are provisioned by a
parent or teacher via the admin-create-user flow and sign in with a
username + password exchanged for Cognito credentials at group-join time.
"""

from __future__ import annotations

import aws_cdk as cdk
from aws_cdk import aws_cognito as cognito
from constructs import Construct


class AuthStack(cdk.Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        env_name: str,
        **kwargs: object,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.user_pool = self._create_user_pool(env_name)
        self.app_client = self._create_app_client(env_name, self.user_pool)

        cdk.CfnOutput(
            self,
            "UserPoolId",
            value=self.user_pool.user_pool_id,
            export_name=f"Dragonfly-UserPoolId-{env_name}",
        )
        cdk.CfnOutput(
            self,
            "AppClientId",
            value=self.app_client.user_pool_client_id,
            export_name=f"Dragonfly-AppClientId-{env_name}",
        )

    def _create_user_pool(self, env_name: str) -> cognito.UserPool:
        return cognito.UserPool(
            self,
            "DragonflyUserPool",
            user_pool_name=f"Dragonfly-{env_name}",
            # Admin-create only. Kids are provisioned by a parent/teacher;
            # parents/teachers are onboarded via an invite-code flow that
            # the API Lambda handles (not self-signup).
            self_sign_up_enabled=False,
            sign_in_aliases=cognito.SignInAliases(
                email=True,
                username=True,  # kids sign in with username (no email)
            ),
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(required=False, mutable=True),
            ),
            custom_attributes={
                "role": cognito.StringAttribute(
                    min_len=1, max_len=16, mutable=True
                ),  # "parent" | "teacher" | "kid"
                "group_id": cognito.StringAttribute(
                    min_len=1, max_len=32, mutable=True
                ),
            },
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_lowercase=True,
                require_digits=True,
                require_symbols=False,
                require_uppercase=False,
            ),
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            mfa=cognito.Mfa.OPTIONAL,
            mfa_second_factor=cognito.MfaSecondFactor(otp=True, sms=False),
            removal_policy=(
                cdk.RemovalPolicy.DESTROY
                if env_name == "dev"
                else cdk.RemovalPolicy.RETAIN
            ),
        )

    def _create_app_client(
        self, env_name: str, pool: cognito.UserPool
    ) -> cognito.UserPoolClient:
        return pool.add_client(
            "DragonflyMobileClient",
            user_pool_client_name=f"Dragonfly-mobile-{env_name}",
            auth_flows=cognito.AuthFlow(
                user_srp=True,              # standard Expo auth flow
                user_password=False,
                admin_user_password=True,   # kid provisioning from API Lambda
            ),
            generate_secret=False,          # mobile public client
            prevent_user_existence_errors=True,
            refresh_token_validity=cdk.Duration.days(30),
            access_token_validity=cdk.Duration.hours(1),
            id_token_validity=cdk.Duration.hours(1),
        )
