# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import importlib
import os
from typing import Any, List, Optional, Tuple

import cdk_nag
from aws_cdk import BundlingOptions, BundlingOutput, DockerImage, Stack, Tags
from aws_cdk import aws_iam as iam
from aws_cdk import aws_s3_assets as s3_assets
from aws_cdk import aws_servicecatalog as servicecatalog
from constructs import Construct


class ServiceCatalogStack(Stack):
    def __init__(
        self,
        scope: Construct,
        id: str,
        portfolio_name: str,
        portfolio_owner: str,
        portfolio_access_role_arn: str,
        prod_account_id: str,
        preprod_account_id: str,
        preprod_region: str,
        prod_region: str,
        dev_vpc_id: str,
        dev_subnet_ids: str,
        pre_prod_vpc_id: str,
        pre_prod_subnet_ids: List[str],
        prod_vpc_id: str,
        prod_subnet_ids: List[str],
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, id, **kwargs)

        self.portfolio_name = portfolio_name
        self.portfolio_owner = portfolio_owner

        self.portfolio = servicecatalog.Portfolio(
            self,
            "Portfolio",
            display_name=portfolio_name,
            provider_name=portfolio_owner,
            description="MLOps Unified Templates",
        )

        account_root_principal = iam.Role(
            self,
            "AccountRootPrincipal",
            assumed_by=iam.AccountRootPrincipal(),
        )
        self.portfolio.give_access_to_role(account_root_principal)

        portfolio_access_role: iam.IRole = iam.Role.from_role_arn(
            self, "portfolio-access-role", portfolio_access_role_arn
        )
        self.portfolio.give_access_to_role(portfolio_access_role)

        product_launch_role = iam.Role(
            self,
            "ProductLaunchRole",
            assumed_by=iam.CompositePrincipal(
                iam.ServicePrincipal("servicecatalog.amazonaws.com"),
                iam.ServicePrincipal("cloudformation.amazonaws.com"),
                iam.ArnPrincipal(portfolio_access_role.role_arn),
            ),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AdministratorAccess")
            ],
        )

        templates_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "templates"
        )
        for template_name in next(os.walk(templates_dir))[1]:
            if template_name == "__pycache__":
                continue
            build_app_asset, deploy_app_asset = self.upload_assets(
                portfolio_access_role=portfolio_access_role,
                template_name=template_name,
            )

            product_stack_module = importlib.import_module(
                f"templates.{template_name}.product_stack"
            )
            product_stack: servicecatalog.ProductStack = product_stack_module.Product(
                self,
                f"{template_name}ProductStack",
                prod_account_id=prod_account_id,
                preprod_account_id=preprod_account_id,
                preprod_region=preprod_region,
                prod_region=prod_region,
                dev_vpc_id=dev_vpc_id,
                dev_subnet_ids=dev_subnet_ids,
                pre_prod_vpc_id=pre_prod_vpc_id,
                pre_prod_subnet_ids=pre_prod_subnet_ids,
                prod_vpc_id=prod_vpc_id,
                prod_subnet_ids=prod_subnet_ids,
                build_app_asset=build_app_asset,
                deploy_app_asset=deploy_app_asset,
            )

            product_name: str = getattr(product_stack, "TEMPLATE_NAME", template_name)
            product_description: Optional[str] = getattr(
                product_stack, "DESCRIPTION", None
            )

            product = servicecatalog.CloudFormationProduct(
                self,
                f"{template_name}CloudFormationProduct",
                owner=portfolio_owner,
                product_name=product_name,
                description=product_description,
                product_versions=[
                    servicecatalog.CloudFormationProductVersion(
                        cloud_formation_template=servicecatalog.CloudFormationTemplate.from_product_stack(
                            product_stack
                        ),
                    )
                ],
            )

            self.portfolio.add_product(product)
            self.portfolio.set_launch_role(product, product_launch_role)

            Tags.of(product).add(key="sagemaker:studio-visibility", value="true")

            cdk_nag.NagSuppressions.add_resource_suppressions(
                portfolio_access_role,
                apply_to_children=True,
                suppressions=[
                    cdk_nag.NagPackSuppression(
                        id="AwsSolutions-IAM5",
                        reason="The role needs wildcard permissions to be able to access template assets in S3",
                    ),
                ],
            )
            cdk_nag.NagSuppressions.add_resource_suppressions(
                product_launch_role,
                suppressions=[
                    cdk_nag.NagPackSuppression(
                        id="AwsSolutions-IAM4",
                        reason=(
                            "Product launch role needs admin permissions in order to be able "
                            "to create resources in the AWS account."
                        ),
                    ),
                ],
            )

    def upload_assets(
        self,
        portfolio_access_role: iam.IRole,
        template_name: str,
    ) -> Tuple[s3_assets.Asset, Optional[s3_assets.Asset]]:
        # Create the build and deployment asset as an output to pass to pipeline stack
        zip_image = DockerImage.from_build("images/zip-image")

        build_app_asset = s3_assets.Asset(
            self,
            f"{template_name}BuildAsset",
            path=f"templates/{template_name}/seed_code/build_app/",
            bundling=BundlingOptions(
                image=zip_image,
                command=[
                    "sh",
                    "-c",
                    """zip -r /asset-output/build_app.zip .""",
                ],
                output_type=BundlingOutput.ARCHIVED,
            ),
        )
        build_app_asset.grant_read(grantee=portfolio_access_role)

        # check if there is a deploy_app folder
        if not os.path.isdir(f"templates/{template_name}/seed_code/deploy_app/"):
            return build_app_asset, None

        deploy_app_asset = s3_assets.Asset(
            self,
            f"{template_name}DeployAsset",
            path=f"templates/{template_name}/seed_code/deploy_app/",
            bundling=BundlingOptions(
                image=zip_image,
                command=[
                    "sh",
                    "-c",
                    """zip -r /asset-output/deploy_app.zip .""",
                ],
                output_type=BundlingOutput.ARCHIVED,
            ),
        )
        deploy_app_asset.grant_read(grantee=portfolio_access_role)

        return build_app_asset, deploy_app_asset
