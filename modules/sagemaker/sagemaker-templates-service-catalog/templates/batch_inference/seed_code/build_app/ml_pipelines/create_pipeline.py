import argparse
import json

from ml_pipelines.model_package import get_approved_package
from ml_pipelines.transformer.pipeline import get_pipeline


def main() -> None:  # pragma: no cover
    parser = argparse.ArgumentParser("Gets the pipeline definition for the pipeline script.")

    parser.add_argument(
        "--role-arn",
        help="IAM Role ARN",
        type=str,
    )
    parser.add_argument(
        "--model-package-group-name",
        help="Model Package Group Name",
        type=str,
    )
    parser.add_argument(
        "--region",
        help="AWS Region",
        type=str,
    )
    parser.add_argument(
        "--artifact-bucket",
        type=str,
    )
    parser.add_argument(
        "--base-job-prefix",
        type=str,
    )
    parser.add_argument(
        "--pipeline-name",
        type=str,
    )
    parser.add_argument(
        "--tags",
        help="""List of dict strings of '[{"Key": "string", "Value": "string"}, ..]'""",
    )
    args = parser.parse_args()

    model_package_arn = get_approved_package(
        region_name=args.region,
        model_package_group_name=args.model_package_group_name,
    )

    pipeline = get_pipeline(
        role_arn=args.role_arn,
        model_package_arn=model_package_arn,
        region=args.region,
        artifact_bucket=args.artifact_bucket,
        base_job_prefix=args.base_job_prefix,
        pipeline_name=args.pipeline_name,
    )

    print("###### SageMaker Pipeline definition:")
    print(pipeline.definition())

    tags = json.loads(args.tags)
    print("###### SageMaker Pipeline tags:")
    print(tags)

    upsert_response = pipeline.upsert(role_arn=args.role_arn, tags=tags)

    print("\n###### Created/Updated SageMaker Pipeline: Response received:")
    print(upsert_response)


if __name__ == "__main__":
    main()
