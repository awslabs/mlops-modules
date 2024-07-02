import json
import os

import boto3

ssm_client = boto3.client("ssm")
codepipeline_client = boto3.client("codepipeline")


def handler(event):
    print("Received event: " + json.dumps(event))

    # unwrap the sagemaker event from SNS message
    if event.get("Records"):
        event = json.loads(
            event.get("Records", [{}])[0].get("Sns", {}).get("Message", "{}")
        )

    # check if this is from sagemaker model approval event
    if (
        not event
        or event.get("source") != "aws.sagemaker"
        or event.get("detail-type") != "SageMaker Model Package State Change"
        or event.get("detail", {}).get("ModelApprovalStatus") != "Approved"
    ):
        print("Not a valid sagemaker model approval event")
        return

    # store the approved model package arn in ssm parameter
    model_package_arn = event["detail"]["ModelPackageArn"]
    # for cross region deployments, model package from original sagemaker artifact bucket is copied to a replica bucket in target region
    model_data_url = event["detail"]["InferenceSpecification"]["Containers"][0][
        "ModelDataUrl"
    ]
    image_uri = event["detail"]["InferenceSpecification"]["Containers"][0]["Image"]
    param_value = json.dumps(
        {
            "modelPackageArn": model_package_arn,
            "modelDataUrl": model_data_url,
            "imageUri": image_uri,
        }
    )
    approved_model_param_name = os.environ["APPROVED_MODEL_PARAM_NAME"]
    ssm_client.put_parameter(
        Name=approved_model_param_name,
        Value=param_value,
        Type="String",
        Overwrite=True,
    )
    print(
        f"Stored model package arn in ssm parameter. {approved_model_param_name=}, {param_value=}"
    )

    # Start the model deploy code pipeline execution
    pipeline_name = os.environ["PIPELINE_NAME"]
    response = codepipeline_client.start_pipeline_execution(name=pipeline_name)
    print(f"Started pipeline execution {response=}")

    return {"statusCode": 200, "body": json.dumps("Pipeline execution started")}
