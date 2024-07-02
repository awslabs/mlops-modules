# Change Log

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

=======

## UNRELEASED

### **Added**

- added `ray-on-eks`, and `manifests/ray-on-eks` manifests
- added a `sagemaker-model-monitoring-module` module with an example of data quality, model quality, model bias, and model explainability monitoring of a SageMaker Endpoint
- added an option to enable data capture in the `sagemaker-endpoint-module`
- added a `personas` example module to deploy various roles required for an AI/ML project
- added `sagemaker-model-cicd` module

### **Changed**

- remove explicit module manifest account/region mappings from `fmops-qna-rag`
- changed ECR encryption to KMS_MANAGED
- changed encryption for each bucket to KMS_MANAGED
- refactor `airflow-dags` module to use Pydantic
- fix inputs for `bedrock-finetuning` module not working
- add `retention-type` argument for the bucket in the `bedrock-finetuning` module
- fix broken dependencies for `examples/airflow-dags`
- use `add_dependency` to avoid deprecation warnings from CDK.
- Various typo fixes.
- Various clean-ups to the SageMaker Service Catalog templates.

## v1.2.0

### **Added**

- added multi-acc sagemaker-mlops manifest example

### **Changed**

- fixed model deploy cross-account permissions
- added bucket and model package group names as stack outputs in the `sagemaker-templates` module
- refactor inputs for the following modules to use Pydantic:
  - `mlflow-fargate`
  - `mlflow-image`
  - `sagemaker-studio`
  - `sagemaker-endpoint`
  - `sagemaker-templates-service-catalog`
  - `sagemaker-custom-kernel`
  - `qna-rag`
- add CDK nag to `qna-rag` module
- rename seedfarmer project name to `aiops`
- chore: adding some missing auto_delete attributes
- chore: Add `auto_delete` to `mlflow-fargate` elb access logs bucket
- updating `storage/ecr` module to latest pending `v1.8.0` of IDF
- enabled ECR image scan on push

## v1.1.0

### **Added**

- added managed autoscaling config to `sagemaker-endpoint` module
- added SSO support in `sagemaker-studio` module
- added VPC/subnets/sg config for multi-account project template to `sagemaker-templates-service-catalog` module
- added `sagemaker-custom-kernel` module
- added batch inference project template to `sagemaker-templates-service-catalog` module
- added EFS removal policy to `mlflow-fargate` module
- added `mwaa` module with example dag which demonstrates the MLOps in Airflow
- added `sagemaker-model-event-bus` module.
- added `sagemaker-model-package-group` module.
- added `sagemaker-model-package-promote-pipeline` module.
- added `sagemaker-hugging-face-endpoint` module
- added `hf_import_models` template to import hugging face models
- added `qna-rag` module
- added `bedrock-finetuning` module

### **Changed**

- reogranized manifests by use-case
- add account/region props for project templates in `sagemaker-templates-service-catalog` module
- fix `sagemaker-templates-service-catalog` model deploy role lookup issue & abalone_xgboost model registry permissions
- update `sagemaker-custom-kernel` module IAM permissions
- split `xgboost_abalone` and `model_deploy` project templates in `sagemaker-templates-service-catalog` module
- add support for other AWS partitions
- update MySQL instance to use T3 instance type
- upgrade `cdk_ecr_deployment` version to fix the deprecated `go1.x` lambda runtime

### **Removed**

- remove AmazonSageMakerFullAccess from `multi_account_basic` template in the `sagemaker-templates-service-catalog` module
- remove AmazonSageMakerFullAccess from `sagemaker-endpoint` module

## v1.0.0

### **Added**

- added `sagemaker-templates-service-catalog` module with `multi_account_basic` project template
- bump cdk & ecr deployment version to fix deprecated custom resource runtimes issue in `mlflow-image`
- added `sagemaker-jumpstart-fm-endpoint` module
- added RDS persistence layer to MLFlow modules
- added `mlflow-image` and `mlflow-fargate` modules
- added `sagemaker-studio` module
- added `sagemaker-endpoint` module
- added `sagemaker-notebook` module

### **Changed**

- refactor validation script to use `ruff` instead of `black` and `isort`

### **Removed**
