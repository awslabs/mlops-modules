# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

from logging import Logger
from typing import Any

import boto3
from botocore.exceptions import ClientError
from config.constants import DEV_REGION, MODEL_PACKAGE_GROUP_NAME

"""Initialise Logger class"""
logger = Logger(name="deploy_stack")

"""Initialise boto3 SDK resources"""
sm_client = boto3.client("sagemaker", region_name=DEV_REGION)


def get_approved_package() -> Any:
    """Gets the latest approved model package for a model package group.
    Returns:
        The SageMaker Model Package ARN.
    """
    try:
        # Get the latest approved model package
        response = sm_client.list_model_packages(
            ModelPackageGroupName=MODEL_PACKAGE_GROUP_NAME,
            ModelApprovalStatus="Approved",
            SortBy="CreationTime",
            MaxResults=100,
        )
        approved_packages = response["ModelPackageSummaryList"]
        # Fetch more packages if none returned with continuation token
        while len(approved_packages) == 0 and "NextToken" in response:
            logger.debug(f"Getting more packages for token: {response['NextToken']}")
            response = sm_client.list_model_packages(
                ModelPackageGroupName=MODEL_PACKAGE_GROUP_NAME,
                ModelApprovalStatus="Approved",
                SortBy="CreationTime",
                MaxResults=100,
                NextToken=response["NextToken"],
            )
            approved_packages.extend(response["ModelPackageSummaryList"])
        # Return error if no packages found
        if len(approved_packages) == 0:
            error_message = f"No approved ModelPackage found for ModelPackageGroup: {MODEL_PACKAGE_GROUP_NAME}"
            logger.error(error_message)
            raise Exception(error_message)
        # Return the pmodel package arn
        model_package_arn = approved_packages[0]["ModelPackageArn"]
        logger.info(f"Identified the latest approved model package: {model_package_arn}")
        return model_package_arn
    except ClientError as e:
        error_message = e.response["Error"]["Message"]
        logger.error(error_message)
        raise Exception(error_message)
