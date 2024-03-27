# Change Log

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

=======

## UNRELEASED

### **Added**

- added EFS removal policy to `mlflow-fargate` module
- added `batch_inference` template to the `sagemaker-templates-service-catalog` module

### **Changed**

- update MySQL instance to use T3 instance type
- fixed the deprecated `go1.x` lambda runtime to use the standard `al2023` runtime

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
