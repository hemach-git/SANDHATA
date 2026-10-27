# Sandhātā AWS Deployment Guide

Version 0.2 | October 26 2026 | Prepared for Hema Chepuri | AWS preparation

AWS is the planned future production destination. The owner has deferred AWS deployment; the family will use this home computer for now. The CHAKRA AWS profile and account are excluded from further Sandhātā work. This guide defines a separate Sandhātā foundation and the steps needed to promote the working local pilot. It does not claim that AWS resources or a public application have been deployed. A future independent AWS setup, application domain, administrator identity and spending limit are required before billable infrastructure is created.

## Proposed family deployment

Use one EC2 instance for Caddy, the web UI, private download API, worker and a private PostgreSQL container. The initial proposal is t3.medium with a 40 GiB encrypted gp3 root volume; final sizing depends on budget and measured memory. Cognito provides invite-only OIDC identities. ECR stores the application image. A private S3 bucket receives encrypted application backups. Secrets Manager holds runtime settings. The single-host design has a host-level outage boundary; it is not a highly available service.

This is a family-sized starting point, not a price quote. EC2 uptime, EBS, public IPv4, S3, Secrets Manager, Cognito usage and any paid model inference contribute to the bill. Region us-east-1 is an example for future planning, not a decision to use an existing project profile. A budget alert is not a hard spending cap. Do not create infrastructure until the account and spending limit are resolved.

## Isolation and permissions

The template creates a new VPC, subnet, route table, internet gateway, security group, instance role, ECR repository, secret, bucket and Cognito pool. Project tags and names identify Sandhātā. It does not reuse or modify CHAKRA instances, databases, buckets or identity pools. Using an existing CLI profile would select an AWS account; it would not justify touching another project's resources.

The security group permits only public TCP 80 and 443. SSH, PostgreSQL, Streamlit, the private API and model ports are not opened. Use Systems Manager for host administration. IMDSv2 is required, with a hop limit of one so bridged application containers do not inherit the host instance credentials by default. The host role can read this stack's ECR repository and application secret and read or write its backup prefix. It has no Bedrock invocation permission.

The backup bucket blocks public access, requires TLS, enables server-side encryption and versions, and expires objects in the backups prefix after seven days. Application-level encrypted archives remain necessary; keep their decryption key separately. ECR image tags are immutable and image scanning is enabled. The user pool, repository, bucket and secret are retained when the stack is deleted, so operator cleanup remains explicit. The EC2 root volume is deleted with its instance; verified off-host backups are essential before storing real career records.

## Infrastructure artifacts

deploy/aws/foundation.json is the CloudFormation foundation. It creates the host and identity resources but does not start the application. Its bootstrap installs Docker and creates private application directories. Compose installation, image publication, database roles, secrets, DNS, model configuration and acceptance are separate release steps. deploy/aws/parameters.example.json deliberately has an invalid placeholder hostname and cannot serve as production configuration unchanged.

deploy/aws/validate.ps1 performs only STS identity lookup and CloudFormation template validation. Pass the chosen profile explicitly. Template validation proves AWS accepts the template syntax; it does not prove IAM deployment permissions, instance availability, application health or end-to-end production readiness.

```powershell
Set-Location -LiteralPath 'C:\Users\Chepuri\Documents\ChatGPT\sandhata'
./deploy/aws/validate.ps1 -AwsProfile SELECTED_PROFILE -Region us-east-1
```

After account, hostname and cost decisions, copy parameters.example.json into the ignored runtime directory and replace the hostname. Inspect a CloudFormation change set before execution. Use a Sandhātā-only stack name such as sandhata-prod and acknowledge CAPABILITY_IAM because the template creates a scoped instance role. Do not execute a stack merely because template validation passed.

## Application deployment sequence

1. Confirm the AWS account, region, domain ownership and monthly spending limit. Verify the intended account with STS and inspect the change set. Create only Sandhātā resources.
2. Point the approved application DNS hostname to the stack's public IPv4 address. Connect to the host through SSM; do not add SSH ingress as a shortcut. Install the official Docker Compose plugin and deploy the reviewed source configuration.
3. Publish the tested application image to the stack's ECR repository using a unique immutable release tag. Review the scan results and use the image digest for deployment. Do not upload runtime data, local .env files or credentials into the image.
4. Add a private PostgreSQL service or a separately approved managed database. Mount encrypted persistent storage, generate new app and worker credentials, and apply schema.sql and admin_schema.sql with a separate migration credential. scripts/migrate.py --schema-only skips the local synthetic identity bootstrap. Do not publish a database port.
5. Configure Streamlit OIDC using the Cognito issuer and generated confidential client. The discovery URL is the issuer plus /.well-known/openid-configuration, not the Cognito login-prefix domain. The registered callback is the application's HTTPS origin plus /oauth2callback. Keep the current provider configuration key named keycloak if using the existing UI login call; that key is an internal alias and can point to Cognito.
6. Retrieve the Cognito client secret privately and create a new cookie secret. Supply runtime/production/secrets.toml and separate app.env and worker.env through the secret workflow. Never put migration, superuser or identity-provider operator credentials in the app environment. Do not reuse the local pilot's account subjects, passwords or cookie secret.
7. Provision the first real administrator as an identity-provider user, verify its stable issuer and subject, and seed its application membership out of band. Use suppressed provider invitation messaging unless an email invitation has been explicitly requested. Each relative then receives an independent identity and an application invitation bound to their verified email.
8. Configure a model endpoint the worker can reach privately, then start Caddy, web, API and worker with the existing production Compose configuration and the chosen database service. Verify DNS and TLS before providing the address to family members.
9. Run synthetic imports, resume upload and private download, an evidence-valid comparison, tracker events, analytics reconciliation, revocation and two-member isolation. Confirm restart persistence and five concurrent sessions on the actual host.
10. Upload an encrypted backup to the stack's private backups prefix, then restore into an isolated target and compare database counts, original file hashes and RLS. Preserve current tombstones and revocation state before any real restoration. Configure a scheduled off-host backup and test recovery before production acceptance.

## Model deployment decision

The working pilot uses local Ollama with gpt-oss:20b. That model does not automatically become available on EC2, and a 4 GiB family host is not sized to run its current local model. The initial AWS template therefore grants no paid inference permission and does not install a model or silently send resumes to a hosted service.

Amazon Bedrock is a possible managed inference adapter. Implement its provider-specific structured-output request, validate the selected model and region, test the same evidence and injection cases, and scope IAM invocation to the approved model or inference profile. Configure costs and an inference budget before activation. This adapter is not implemented or live-tested by the infrastructure foundation. A separately sized private Ollama host is the open-source alternative and has its own compute cost. App search and tracking must remain usable during model outages.

## Verification and remaining inputs

AWS CLI is installed. Preliminary read-only identity and template syntax checks succeeded before deployment was deferred. No AWS resource was created. The final foundation is checked offline with cfn-lint; validation results are in deliverables/verification/aws_template_validation.json. No further calls use CHAKRA. The future validation script requires an explicit profile and refuses the profile named chakra. Revalidate the final template using the future independent account before deployment.

Before promotion, record the actual stack outputs privately, deployed Git SHA and image digest, release checks, backup restore evidence and owner acceptance. The remaining owner inputs are account/profile selection, actual DNS hostname, spending limit, administrator identity and model hosting choice. These are future configuration and cost decisions. Current operation remains local to the home computer; a future AWS setup does not alter that choice until deployment work resumes.

## AWS references

- Cognito OIDC and login domains: https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-pools-assign-domain.html
- Cognito confidential OAuth clients: https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-cognito-userpoolclient.html
- EC2 metadata protection: https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-properties-ec2-instance-metadataoptions.html
- Docker on Amazon Linux: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-docker.html
- Bedrock structured outputs: https://docs.aws.amazon.com/bedrock/latest/userguide/structured-output.html
