from logging import Logger
from typing import Optional

import boto3
from botocore.exceptions import ClientError

"""Initialise Logger class"""
logger = Logger(name="deploy_stack")


def get_approved_package(region_name: str, model_package_group_name: str) -> Optional[str]:
    """Gets the latest approved model package for a model package group.
    Returns:
        The SageMaker Model Package ARN.
    """
    sm_client = boto3.client("sagemaker", region_name=region_name)

    try:
        # Get the latest approved model package
        response = sm_client.list_model_packages(
            ModelPackageGroupName=model_package_group_name,
            ModelApprovalStatus="Approved",
            SortBy="CreationTime",
            MaxResults=100,
        )
        approved_packages = response["ModelPackageSummaryList"]

        # Fetch more packages if none returned with continuation token
        while len(approved_packages) == 0 and "NextToken" in response:
            logger.debug(f"Getting more packages for token: {response['NextToken']}")
            response = sm_client.list_model_packages(
                ModelPackageGroupName=model_package_group_name,
                ModelApprovalStatus="Approved",
                SortBy="CreationTime",
                MaxResults=100,
                NextToken=response["NextToken"],
            )
            approved_packages.extend(response["ModelPackageSummaryList"])

        # Return None if no packages found
        if len(approved_packages) == 0:
            error_message = f"No approved ModelPackage found for ModelPackageGroup: {model_package_group_name}"
            logger.warning(error_message)
            return None

        # Return the pmodel package arn
        model_package_arn = approved_packages[0]["ModelPackageArn"]
        logger.info(f"Identified the latest approved model package: {model_package_arn}")
        return model_package_arn  # type: ignore[no-any-return]

    except ClientError as e:
        error_message = e.response["Error"]["Message"]
        logger.error(error_message)
        raise Exception(error_message)
