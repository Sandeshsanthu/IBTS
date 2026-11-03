Instant Bank Transfer Switch — Technical README
1. Overview
The Instant Bank Transfer Switch is a mobile payment switching application that receives a payment request, routes it intelligently to the appropriate bank or payment rail, and returns an instant confirmation response.

The system supports:

Real-time payment request processing
Intelligent routing to banks or payment rails
Idempotency and duplicate payment protection
Retry, timeout, and circuit breaker handling
Transaction state tracking
Asynchronous settlement processing
Redis-based caching and rate limiting
AWS-managed persistence and messaging
2. High-Level Architecture
Request flow:

GLB → API Gateway → Payment Switch → Payment Router → Bank Adapter → Bank / Payment Rail

Supporting components:

Redis: Used for API rate limiting, routing cache, and fast temporary lookups.
AWS DynamoDB: Used for idempotency records, transaction records, and routing configuration.
Amazon SQS: Used for asynchronous settlement event publishing.
Mock Bank Server: Used for local/testing bank endpoint simulation.
OpenTelemetry: Used for tracing and log correlation across services.
3. Core Services
The platform contains five main application services:

API Gateway
Payment Switch
Payment Router
Idempotency Guard
Bank Adapter
Redis and AWS services support these application services.

4. API Gateway
The API Gateway is the external entry point for payment requests.

Responsibilities
Authenticate incoming requests
Validate the request body and API contract
Validate the request ID and idempotency key
Apply rate limiting using Redis
Forward valid requests to the Payment Switch
Return the final response to the client
Key dependency
Redis is used for rate limiting by IP and VPA.
5. Payment Switch
The Payment Switch is the main orchestration layer for payment processing.

Responsibilities
Validate idempotency through the Idempotency Guard
Create a transaction record
Request route selection from the Payment Router
Call the selected bank flow through the Bank Adapter
Process the bank response
Update transaction state
Publish settlement events to Amazon SQS
Return an instant response to the API Gateway
Common transaction states
Created
Processing
Success
Failed
Timeout
Duplicate
Pending settlement
6. Idempotency Guard
The Idempotency Guard prevents duplicate payment processing.

Responsibilities
Store idempotency records in AWS DynamoDB
Detect duplicate requests using the idempotency key
Return the original result for repeated requests where applicable
Prevent double debit when a retry happens after timeout or lost response
Maintain idempotency records for the configured TTL period
Example scenario
A customer sends a ₹100 debit request. The bank processes the transaction, but the response is lost due to timeout. If the client retries with the same idempotency key, the system must not debit the customer again.

7. Payment Router
The Payment Router selects the most suitable bank or payment rail for the transaction.

Routing decision factors
Bank availability
Latency
Error rate
Timeout rate
Maintenance status
Transaction type
Bank or PSP compatibility
Responsibilities
Read routing configuration from AWS DynamoDB
Cache routing data in Redis
Evaluate route health and eligibility
Select the best available bank or payment rail
Return the selected route to the Payment Switch
Key dependency
Redis is used to cache routing rules and reduce repeated DynamoDB lookups.
8. Bank Adapter
The Bank Adapter connects the internal switch platform to external bank endpoints.

Responsibilities
Accept payment instructions from internal services
Translate the internal request format into the bank-specific protocol
Execute bank API calls with timeout handling
Support fallback timeout configuration
Support hedged requests where configured
Apply circuit breaker logic
Return a normalized bank response to the Payment Switch
Reliability controls
Primary timeout
Fallback timeout
Circuit breaker failure threshold
Circuit breaker reset timeout
9. Redis Usage
Redis is a shared infrastructure component used for fast, temporary operations.

Redis is used for:

API rate limiting
Per-IP request limit tracking
Per-VPA request limit tracking
Routing cache for the Payment Router
Fast lookup for frequently accessed routing data
Redis improves response time and reduces repeated reads from AWS DynamoDB.

10. AWS Services
The platform uses AWS-managed services for persistence and messaging.

AWS DynamoDB
DynamoDB is used for:

Idempotency records
Transaction records
Routing configuration
Amazon SQS
Amazon SQS is used for:

Asynchronous settlement event publishing
Decoupling settlement processing from the instant customer response
11. End-to-End Payment Flow
Mobile client sends a payment request.
GLB forwards the request to the API Gateway.
API Gateway authenticates and validates the request.
API Gateway applies Redis-based rate limiting.
API Gateway forwards the request to the Payment Switch.
Payment Switch validates idempotency through the Idempotency Guard.
Idempotency Guard checks AWS DynamoDB for duplicate request records.
Payment Switch creates a transaction record in AWS DynamoDB.
Payment Switch requests routing from the Payment Router.
Payment Router checks Redis cache and AWS DynamoDB routing data.
Payment Router selects the best available bank or payment rail.
Payment Switch sends the request to the Bank Adapter.
Bank Adapter calls the selected bank endpoint.
Bank response is returned to the Payment Switch.
Payment Switch updates transaction state in AWS DynamoDB.
Payment Switch publishes a settlement event to Amazon SQS.
API Gateway returns an instant confirmation response to the client.
12. Resilience Design
The system includes the following resilience mechanisms:

Idempotency: Prevents duplicate debit during retries.
Redis rate limiting: Protects the API from excessive requests.
Timeout handling: Prevents slow bank responses from blocking processing.
Retry handling: Supports controlled retry scenarios.
Circuit breaker: Stops traffic to unhealthy bank endpoints.
Routing intelligence: Avoids banks with poor availability, high latency, high error rate, high timeout rate, or maintenance status.
Asynchronous settlement: Keeps the customer response fast while settlement continues separately.
Health checks: Services expose health endpoints for availability monitoring.
13. Runtime Components
Application services
API Gateway
Payment Switch
Payment Router
Idempotency Guard
Bank Adapter
Infrastructure components
Redis
AWS DynamoDB
Amazon SQS
Mock Bank Server
OpenTelemetry Collector
Only the API Gateway is externally exposed. Internal services communicate over the private service network.

14. Deployment Notes
The application is containerized and runs as multiple services. Each service has its own responsibility and communicates with other services through internal service URLs.

The API Gateway is the public-facing service. Other services remain internal and are accessed only within the private network.

Docker images are maintained separately for each application service:

API Gateway image
Payment Switch image
Payment Router image
Idempotency Guard image
Bank Adapter image
15. DevOps Section Placeholder
Add DevOps details in this section:

CI/CD pipeline
Docker image build and push process
Deployment strategy
AWS environment configuration
Secrets management
Monitoring and alerting
Rollback strategy
Infrastructure provisioning
Production readiness checklist

Infrastructure Technical Design
Overview
The IBTS infrastructure is provisioned on AWS using Terraform and runs on Amazon EKS. The infrastructure is split into multiple Terraform stages so that core networking, cluster setup, platform configuration, load balancing, and GitOps deployment can be managed independently.
The infrastructure supports:

Amazon EKS for container orchestration
AWS VPC with public and private subnets
Redis for application cache and rate limiting
AWS DynamoDB for application persistence
Amazon SQS for asynchronous settlement events
IAM Roles for Service Accounts for pod-level AWS access
Karpenter for dynamic worker node provisioning
AWS Application Load Balancer for external API access
Argo CD for GitOps-based application deployment
OpenTelemetry-ready configuration for observability


Terraform Stage Overview



Stage
Purpose




Stage 1
Creates the VPC, subnets, EKS cluster, node groups, routing, NAT gateways, and VPC endpoints


Stage 2
Configures EKS add-ons, IAM Roles for Service Accounts, namespaces, DynamoDB, SQS, and shared application config


Stage 3
Creates the external Application Load Balancer and binds it to the API Gateway Kubernetes service


Stage 4
Installs Argo CD and bootstraps the IBTS application from Git




Stage 1: EKS Cluster and Network Foundation
Stage 1 creates the core AWS infrastructure required to run the IBTS platform.
Main Components

AWS VPC
Public subnets
Private subnets
Internet Gateway
NAT Gateways
Public and private route tables
VPC endpoints
Amazon EKS cluster
System node group

Region and Environment
The infrastructure is configured for the AWS Mumbai region:

AWS Region: ap-south-2
Environment: poc
Cluster name: ibts-eks
Kubernetes version: 1.31

Terraform state is stored in an encrypted S3 backend. Stage 2 reads the Stage 1 remote state to connect to the EKS cluster and reuse cluster outputs.

VPC and Subnet Design
The VPC uses the CIDR range 10.0.0.0/16.
The network is deployed across 2 Availability Zones:

ap-south-2a
ap-south-2b

Subnet design:



Subnet Type
Purpose




Public subnets
Host internet-facing AWS load balancer resources and NAT gateways


Private subnets
Host EKS worker nodes and application workloads



Public subnets are tagged for external load balancers. Private subnets are tagged for internal load balancers and Karpenter node discovery.

NAT Gateway and Routing
Each Availability Zone has a NAT Gateway in the public subnet. Private route tables send outbound internet traffic through the NAT Gateway in the same Availability Zone.
This design allows private EKS workloads to access external endpoints without exposing worker nodes directly to the internet.

VPC Endpoints
The infrastructure includes VPC endpoints to reduce dependency on NAT Gateway traffic for supported AWS services.
Configured endpoints:



AWS Service
Endpoint Type
Purpose




Amazon ECR API
Interface
Pull container image metadata privately


Amazon ECR Docker
Interface
Pull container images privately


Amazon DynamoDB
Gateway
Access DynamoDB from private subnets


Amazon S3
Gateway
Access S3 from private subnets


Amazon SQS
Interface
Access SQS from private subnets



The interface endpoints use a dedicated security group that allows HTTPS traffic from within the VPC CIDR.

Amazon EKS Cluster
The EKS cluster is deployed into private subnets.
Key configuration:

Public and private API endpoint access are enabled.
IAM Roles for Service Accounts is enabled.
Cluster authentication uses API and ConfigMap mode.
Cluster logs are enabled for API and audit logs.
Cluster resources are tagged for Karpenter discovery.

The EKS cluster is the main runtime platform for all IBTS application services.

System Node Group
A system node group is configured to run core infrastructure workloads.
Key characteristics:

On-demand capacity
Fixed size of one node
Instance type: t3.medium
Used for critical system add-ons
Tainted with CriticalAddonsOnly=true:NoSchedule

The taint helps prevent application workloads from being scheduled on the system node. Application workloads are expected to run on Karpenter-managed worker nodes.

Stage 2: Cluster Configuration and Platform Services
Stage 2 configures the EKS cluster after the cluster has been created.
Stage 2 uses Terraform remote state from Stage 1 to retrieve:

Cluster name
Cluster endpoint
Cluster certificate authority data
OIDC provider details
VPC ID
Subnet IDs
Security group IDs

The Kubernetes, Helm, and Kubectl providers use AWS EKS token execution so that long Terraform applies do not fail due to expired static tokens.

IAM Roles for Service Accounts
IAM Roles for Service Accounts are used to give Kubernetes services least-privilege AWS permissions without storing static AWS credentials in pods.
Configured roles include:



Service Account
Namespace
AWS Access




ebs-csi-controller-sa
kube-system
Amazon EBS CSI permissions


aws-load-balancer-controller
kube-system
AWS Load Balancer Controller permissions


payment-switch
ibts-app
DynamoDB transaction table and SQS settlement queue


payment-router
ibts-app
DynamoDB routing table read access


idempotency-guard
ibts-app
DynamoDB idempotency table access



This design keeps AWS permissions scoped to the services that need them.

Karpenter Configuration
Karpenter is used to dynamically provision worker nodes for application workloads.
The infrastructure configures:

Karpenter interruption SQS queue
EventBridge rules for spot interruption warnings
EventBridge rules for rebalance recommendations
EventBridge rules for EC2 instance state changes
Karpenter node IAM role
Karpenter instance profile
EKS access entry for Karpenter nodes
Karpenter controller IAM role
Karpenter controller service account

The Karpenter node role includes permissions for:

EKS worker node operation
Amazon VPC CNI
Amazon ECR image pull
AWS Systems Manager access

Karpenter is configured to support spot-based application capacity, while the system node group remains on on-demand capacity for core infrastructure stability.

EKS Add-ons
Stage 2 installs and configures core EKS add-ons.
Configured add-ons:



Add-on
Purpose




EKS Pod Identity Agent
Supports pod identity capabilities


CoreDNS
Cluster DNS resolution


kube-proxy
Kubernetes network proxy


VPC CNI
Pod networking inside the VPC


AWS EBS CSI Driver
Persistent volume provisioning using Amazon EBS



CoreDNS is configured with tolerations so it can run on the system node group.

Storage Configuration
A default gp3 Kubernetes StorageClass is created.
Key configuration:

Provisioner: Amazon EBS CSI driver
Volume type: gp3
Encryption enabled
Volume expansion enabled
Reclaim policy: Retain
Binding mode: WaitForFirstConsumer

This allows persistent volumes to be created only after Kubernetes knows where the consuming pod will be scheduled.

AWS Load Balancer Controller
The AWS Load Balancer Controller is installed through Helm.
It is configured with:

EKS cluster name
AWS region
VPC ID from Stage 1
Dedicated IAM role through IRSA
System node toleration
System node selector

The controller is used by Kubernetes resources that need AWS load balancer integration.

Metrics Server
Metrics Server is installed through Helm in the kube-system namespace.
It provides resource metrics for Kubernetes workloads and supports autoscaling and operational visibility.

Kubernetes Namespaces
The infrastructure creates 2 main namespaces:



Namespace
Purpose




ibts-app
Application services such as API Gateway, Payment Switch, Payment Router, Idempotency Guard, Bank Adapter, Redis, and mock bank components


ibts-observability
Observability tools such as OpenTelemetry, metrics, logging, dashboards, and tracing components



Resource quotas and limit ranges are configured for both namespaces to control CPU, memory, and pod usage.

Application Namespace Controls
The ibts-app namespace includes:

Resource quota
Limit range
Service accounts for application workloads
IRSA annotations for AWS-integrated services

The limit range applies default CPU and memory requests and limits when workloads do not define them explicitly.

Observability Namespace Controls
The ibts-observability namespace includes:

Resource quota sized for observability workloads
Limit range for default requests and limits
Capacity for tools such as Prometheus, Grafana, OpenTelemetry Collector, Jaeger, Elasticsearch, Kibana, and Fluent Bit if deployed by the application manifests

This namespace separates platform observability components from application runtime services.

AWS DynamoDB Tables
The infrastructure provisions DynamoDB tables used by the IBTS application.



Table
Used By
Purpose




IdempotencyRecords
Idempotency Guard
Stores idempotency keys and prevents duplicate payment processing


ibts-transactions
Payment Switch
Stores payment transaction records and transaction state


routing-table
Payment Router
Stores bank and payment rail routing configuration



The idempotency table has TTL enabled using the expiry_time attribute.
The transaction table includes a secondary index on transaction status to support status-based queries.
All tables use on-demand billing mode.

Amazon SQS Queues
The infrastructure provisions SQS resources for asynchronous processing.
Settlement Queue
The settlement queue is used by the Payment Switch to publish settlement events without blocking the instant customer response.
Queue name:

ibts-settlement-events

Key configuration:

Message retention: 1 day
Visibility timeout: 30 seconds
Server-side encryption enabled
Dead-letter queue configured

Settlement Dead-Letter Queue
The settlement DLQ stores failed messages after repeated processing failures.
Queue name:

ibts-settlement-events-dlq

The redrive policy sends messages to the DLQ after maxReceiveCount reaches 3.

Shared Application Configuration
Stage 2 creates a shared Kubernetes ConfigMap for IBTS application services.
The ConfigMap provides:

AWS region
DynamoDB endpoint
DynamoDB table names
SQS queue name
SQS endpoint
OpenTelemetry endpoint
Internal service URLs
Redis host and port
Mock bank server URL

This keeps service configuration centralized and avoids hardcoding runtime endpoints inside application images.

Redis Configuration
Redis is used by the application for fast temporary data access.
Primary uses:

API Gateway rate limiting
Per-IP request tracking
Per-VPA request tracking
Routing cache for the Payment Router
Fast lookup for frequently accessed routing data

The shared configuration points application services to the internal Redis service in the ibts-app namespace.

OpenTelemetry Configuration
Application services are configured to send traces to the OpenTelemetry Collector through the shared ConfigMap.
The configured OpenTelemetry settings include:

OTLP exporter endpoint
OTLP protocol
Trace exporter
Log correlation flag

This supports distributed tracing across API Gateway, Payment Switch, Payment Router, Idempotency Guard, and Bank Adapter.

Stage 3: External Load Balancer
Stage 3 creates an AWS Application Load Balancer to expose the API Gateway externally.
Main components:

Public Application Load Balancer
ALB security group
Target group for API Gateway
HTTP listener on port 80
TargetGroupBinding for Kubernetes service integration
Security group rule allowing ALB traffic to API Gateway pods

The ALB forwards traffic to the API Gateway Kubernetes service on port 8084.
Health checks use:

Path: /actuator/health
Protocol: HTTP
Port: traffic port
Expected response: 200

The target group uses IP target mode, which allows traffic to route directly to pods.

API Exposure Model
Only the API Gateway is externally exposed through the ALB.
Internal services remain private inside the Kubernetes cluster:

Payment Switch
Payment Router
Idempotency Guard
Bank Adapter
Redis
Mock Bank Server
Observability services

This keeps the external attack surface limited to the API Gateway.

Stage 4: Argo CD and GitOps Deployment
Stage 4 installs Argo CD using Helm.
Argo CD is deployed into the argocd namespace.
Key configuration:

Argo CD server uses ClusterIP service type
ApplicationSet is enabled
Dex is disabled
Notifications are disabled
Kustomize load restrictions are relaxed to allow the application kustomization to reference files outside its base folder

Stage 4 also installs the Argo CD application bootstrapper using the argocd-apps Helm chart.
The bootstrapper creates the IBTS application definition and points Argo CD to the configured Git repository, revision, and application path.

GitOps Application Deployment
The Argo CD application deploys IBTS workloads into the ibts-app namespace.
The sync policy supports:

Namespace creation
Optional automated sync
Optional pruning
Self-healing when automated sync is enabled
Drift ignore rules for rollout restart annotations

This allows application deployment to be managed from Git while Terraform manages the underlying infrastructure.

Security Design
The infrastructure applies the following security controls:

Application workloads run in private subnets.
Only the API Gateway is exposed externally through the ALB.
AWS permissions are assigned through IRSA instead of static credentials.
Service-specific IAM policies are used for Payment Switch, Payment Router, and Idempotency Guard.
SQS queues use server-side encryption.
EBS volumes are encrypted through the default gp3 StorageClass.
Terraform state is stored in an encrypted S3 backend.
Kubernetes namespaces use resource quotas and limit ranges.
System workloads are isolated using node labels and taints.


Runtime Traffic Flow
The runtime infrastructure flow is:

User or client sends a payment request to the external ALB.
ALB forwards the request to the API Gateway service in EKS.
API Gateway validates and forwards the request to the Payment Switch.
Payment Switch checks idempotency through Idempotency Guard.
Idempotency Guard reads and writes idempotency data in DynamoDB.
Payment Switch requests route selection from Payment Router.
Payment Router uses Redis cache and DynamoDB routing data.
Payment Switch sends the selected payment request to the Bank Adapter.
Bank Adapter calls the selected bank endpoint or mock bank endpoint.
Payment Switch updates transaction state in DynamoDB.
Payment Switch publishes settlement events to Amazon SQS.
API Gateway returns the instant response to the client.


Deployment Order
The infrastructure is intended to be applied in this order:

Stage 1: EKS cluster and network foundation
Stage 2: Cluster configuration, platform services, AWS app resources, and shared config
Stage 3: External ALB and API Gateway target binding
Stage 4: Argo CD installation and GitOps application bootstrap

This order is required because later stages depend on resources and outputs created by earlier stages.

Operational Notes

Stage 2 depends on Stage 1 remote state.
The API Gateway is exposed through the ALB on HTTP port 80.
Production environments should restrict allowed CIDRs as needed.
Production environments should use HTTPS/TLS for external traffic.
Sensitive values such as JWT secret, API key, and Grafana password should be supplied securely through CI variables or a secrets manager.
Redis is referenced through shared application configuration and is expected to be available inside the ibts-app namespace.
Karpenter is used for dynamic node provisioning, while the system node group provides stable on-demand capacity for core add-ons.

CI/CD Pipelines
Overview
IBTS uses GitHub Actions for CI/CD across application services, AWS infrastructure, Kubernetes platform configuration, GitOps deployment, load balancer provisioning, and observability setup.
The CI/CD design supports:

Pull request validation
Static code checks
Unit testing with coverage gates
Docker image build and push
Image digest audit trail
Kubernetes manifest updates
Terraform-based infrastructure deployment
Argo CD GitOps bootstrap
Load balancer deployment and health validation
Observability stack deployment
Manual destroy workflow with safety confirmation


Pipeline Inventory



Workflow
Trigger
Purpose




PR Checks
Push, pull request, manual
Runs changed-service validation, lint, SAST, unit tests, Docker build, and PR summary


IBTS Build, Test, and Push
Push to main, manual
Builds application images, pushes to Docker Hub, captures digest audit records, and updates Kubernetes manifests


IBTS Infrastructure
Manual
Runs Terraform Stage 1 and Stage 2 for EKS, networking, add-ons, AWS resources, and cluster configuration


IBTS Load Balancer
Manual
Creates or destroys the external Application Load Balancer and binds it to the API Gateway service


IBTS ArgoCD Deployment
Manual
Installs, updates, or removes Argo CD and bootstraps the IBTS GitOps application


Terraform Destroy
Manual only
Destroys Stage 2 Kubernetes configuration first, then destroys Stage 1 cluster and VPC resources


IBTS Observability
Manual
Deploys metrics, logging, and tracing stack into the observability namespace


IBTS Dashboard
Manual
Imports or updates observability dashboards


IBTS ArgoCD Status
Manual
Read-only validation of Argo CD sync status, health, drift, and controller details




PR Checks Pipeline
The PR checks pipeline validates service changes before merge.
Trigger
Runs on:

Push to main
Push to develop
Pull requests targeting main or develop
Manual workflow dispatch

Changed Service Detection
The pipeline uses path filtering to detect changes in:

API Gateway
Payment Switch
Payment Router
Bank Adapter
Idempotency Guard
Shared package

This allows checks to run only for services affected by a change.
Linting
Linting is performed using Ruff.
Key behavior:

Runs per changed service
Uses the shared Ruff configuration
Produces GitHub-formatted output
Runs as a non-blocking check

Lint failures are reported but do not block merge.
SAST
Static application security testing is performed using Bandit.
Key behavior:

Runs per changed service
Generates JSON reports
Uploads reports as workflow artifacts
Runs as a non-blocking check

Bandit findings are advisory and do not block merge.
Unit Tests
Unit tests are blocking.
Key behavior:

Runs per changed service
Installs the shared package
Installs service dependencies
Runs pytest
Generates coverage XML
Generates JUnit XML
Enforces 80% coverage threshold

If tests or the coverage gate fail, the PR check fails.
Docker Build
The PR pipeline builds Docker images but does not push them.
Purpose:

Validate Dockerfile correctness
Validate build context
Catch container build issues before merge

PR Summary
The pipeline posts or updates a PR comment with the results of:

Lint
SAST
Unit tests
Docker build

Coverage reports, JUnit test results, and Bandit reports are uploaded as artifacts.

Application Build, Test, and Push Pipeline
The main application CI pipeline builds and publishes the IBTS service images.
Trigger
Runs on:

Push to main
Manual workflow dispatch

The workflow is triggered when changes are made to:

API Gateway
Bank Adapter
Payment Switch
Payment Router
Idempotency Guard
Shared package
CI workflow file

Pipeline Stages
The application CI pipeline includes:

Ruff linting
Bandit SAST
Secret scanning
Unit tests
Docker build and push
Image digest audit record creation
Kubernetes manifest update

Secret Scan
Secret scanning is performed using TruffleHog.
Key behavior:

Scans changes between base and head commits
Reports only verified findings
Runs as an advisory check

Unit Test Gate
Unit tests run for each application service.
Test configuration includes:

Python 3.12
Shared package installation
Service-level dependencies
pytest
pytest coverage
JUnit output
80% coverage threshold

If a service has no tests, the workflow skips the coverage gate for that service.
Docker Image Build and Push
The pipeline builds and pushes Docker images for:

API Gateway
Bank Adapter
Payment Switch
Payment Router
Idempotency Guard

Each image is pushed with two tags:

latest
Git commit SHA

The Git SHA tag provides traceability between source code, container image, and deployment.
Image Digest Audit
After each image push, the workflow creates an audit record containing:

Service name
Git SHA
Git ref
Actor
Build timestamp
Image tags
Image digest

Digest audit records are uploaded as artifacts and retained for audit purposes.
Kubernetes Manifest Update
After successful image build and push, the workflow updates Kubernetes image tags to the Git SHA.
This supports GitOps deployment by ensuring Kubernetes manifests reference immutable image versions instead of relying only on latest.

Terraform Infrastructure Pipeline
The infrastructure pipeline provisions the core AWS and EKS platform using Terraform.
Trigger
Runs manually through workflow dispatch.
Authentication
The workflow authenticates to AWS using GitHub Actions OIDC and an AWS IAM role. This avoids storing long-lived AWS access keys in GitHub secrets.
Terraform Version
The workflow uses Terraform 1.10.5.
State Lock Handling
The workflow configures Terraform lock timeouts for plan and apply operations. This allows Terraform to wait for the remote state lock instead of failing immediately.
Stage 1: Cluster Plan and Apply
Stage 1 provisions the foundational infrastructure.
Includes:

VPC
Public subnets
Private subnets
Internet Gateway
NAT Gateways
Route tables
VPC endpoints
EKS cluster
System node group

Stage 1 runs as:

Terraform init
Terraform validate
Terraform plan
Upload plan artifact
Download plan artifact
Terraform apply

The apply job uses the exact plan generated by the plan job.
Stage 2: Add-ons and Platform Configuration
Stage 2 configures the EKS cluster and application platform dependencies.
Includes:

Kubernetes provider configuration
Helm provider configuration
EKS add-ons
EBS CSI driver
AWS Load Balancer Controller
Metrics Server
Namespaces
Resource quotas
Limit ranges
IRSA roles
DynamoDB tables
SQS queues
Shared application ConfigMap

Stage 2 runs after Stage 1 completes.
Karpenter Cleanup
Before Stage 2 apply, the workflow checks the Karpenter Helm release state.
If Karpenter is stuck in a failed or pending state, the workflow uninstalls the release before applying Terraform. This prevents failed Helm states from blocking the next apply.

Load Balancer Pipeline
The load balancer pipeline manages the external Application Load Balancer for the API Gateway.
Trigger
Runs manually through workflow dispatch.
Supported actions:

Apply
Destroy

Preflight Checks
Before apply, the workflow verifies:

TargetGroupBinding CRD exists
API Gateway Kubernetes service exists
API Gateway has ready endpoints

If the API Gateway does not have ready endpoints, the workflow stops before Terraform runs.
Terraform Actions
The workflow runs:

Terraform init
Terraform format check
Terraform validate
Terraform plan
Upload plan artifact
Download plan artifact
Terraform apply

For destroy, the workflow creates a destroy plan and applies it.
Health Validation
After apply, the workflow waits for ALB targets to become healthy.
It then performs a smoke test against the API Gateway health endpoint through the ALB.
Failure Diagnostics
If validation fails, the workflow collects:

TargetGroupBinding details
AWS Load Balancer Controller logs
Target group health information


Argo CD Deployment Pipeline
The Argo CD pipeline installs or removes Argo CD and bootstraps the IBTS GitOps application.
Trigger
Runs manually through workflow dispatch.
Supported actions:

Apply
Destroy

Inputs
The workflow accepts:

Confirmation input
Action
Argo CD Helm chart version
Argo CD apps chart version
Auto-sync flag
Auto-prune flag

Preflight Validation
The pipeline performs checks before Terraform plan.
Checks include:

Confirm input is set to yes
Auto-prune is only used with auto-sync
Repository visibility is compatible with the Argo CD configuration
Terraform backend is configured
EKS cluster access works
GitHub Actions role has cluster-admin permissions
Required bootstrap objects exist
ServiceMonitor CRD availability is checked
Helm chart versions exist
Kustomize build succeeds
Rendered manifests do not include Kubernetes Secret objects from Git

Terraform Plan and Apply
The workflow creates a Terraform plan for either apply or destroy.
The plan artifact includes the Terraform lock file so the apply job uses the same provider versions as the plan job.
Post-Apply Validation
After Argo CD is installed, the workflow verifies:

Argo CD server rollout
Argo CD repo server rollout
Argo CD ApplicationSet controller rollout
Argo CD application controller rollout
Kustomize build options in argocd-cm
IBTS application sync status
IBTS application health status
Application conditions and managed resources

Failure Diagnostics
If the apply fails, the workflow collects:

Argo CD pods and services
Argo CD server logs
Argo CD repo server logs
IBTS Argo CD application description


Terraform Destroy Pipeline
The destroy workflow is manual only and includes a safety confirmation.
Safety Confirmation
The workflow requires the user to type DESTROY.
If the input does not match exactly, the workflow stops.
Destroy Order
The destroy order is important:

Destroy Stage 2 Kubernetes and platform configuration
Destroy Stage 1 EKS cluster, networking, and VPC resources

Stage 2 must be destroyed first because Kubernetes resources require the cluster to exist during deletion.
State Cleanup
The workflow removes orphaned Kubernetes and Helm state references before destroy. This helps avoid failures caused by resources that no longer exist in the cluster.
Lock Behavior
The destroy commands use lock bypass behavior to handle state lock issues during teardown.
This should be used carefully because disabling locks can be risky if another Terraform run is active.

Observability Pipeline
The observability pipeline deploys metrics, logging, and tracing components.
Trigger
Runs manually through workflow dispatch.
Preflight Checks
The workflow:

Authenticates to AWS using OIDC
Verifies AWS identity
Confirms EKS cluster status
Updates kubeconfig
Lists cluster nodes
Requires the Grafana admin password secret

If the Grafana password secret is missing, the workflow stops to avoid using an unsafe fallback value.
Deployment
The workflow runs the observability deployment script.
The observability stack is deployed into the ibts-observability namespace.
Failure Diagnostics
If deployment fails, the workflow collects:

Pods
Persistent volume claims
Resource quota details
Recent namespace events
Helm release status


Dashboard Pipeline
The dashboard pipeline imports or updates dashboards for the observability stack.
Trigger
Runs manually through workflow dispatch.
Deployment
The workflow:

Authenticates to AWS
Connects to EKS
Requires the Grafana admin password secret
Runs the dashboard import script

Failure Diagnostics
On failure, it collects observability namespace state and Helm release details.

Argo CD Status Pipeline
The Argo CD status workflow is read-only and used for operational checks.
Trigger
Runs manually through workflow dispatch.
Checks
The workflow:

Connects to the EKS cluster
Refreshes the IBTS Argo CD application
Waits for sync and health status
Checks whether ignore differences configuration is present
Prints the latest Argo CD operation state
Runs Argo CD diff in core mode
Prints deployment field managers
Searches controller logs for selected application resources

This workflow is useful for diagnosing GitOps drift, sync issues, and controller behavior.

CI/CD Security Controls
The pipelines include the following controls:

AWS authentication uses GitHub Actions OIDC.
Long-lived AWS access keys are not required in GitHub Actions.
GitHub environments are used for infrastructure workflows.
Terraform plan and apply are separated.
Terraform apply uses uploaded plan artifacts.
Manual confirmation is required for infrastructure, Argo CD, load balancer, observability, and destroy workflows.
Destroy requires exact DESTROY confirmation.
Docker Hub credentials are stored in GitHub secrets.
Grafana admin password is required through GitHub secrets.
Secret scanning runs in the application CI pipeline.
Image digest records are generated for audit traceability.
Kubernetes manifests are updated with Git SHA image tags.
Lint and SAST are advisory, while tests and Docker builds are blocking.


Deployment Flow
The expected deployment flow is:

Developer opens or updates a pull request.
PR checks run lint, SAST, tests, Docker build, and PR summary.
After merge to main, the application CI pipeline builds and pushes service images.
The pipeline records image digests for audit.
The pipeline updates Kubernetes manifests with the new Git SHA image tags.
Terraform infrastructure workflows provision or update AWS and EKS resources when required.
Argo CD deploys the application from Git.
The load balancer workflow exposes the API Gateway after the service has ready endpoints.
Observability and dashboard workflows deploy monitoring, logging, tracing, and dashboard configuration.
The Argo CD status workflow can be used to validate sync and health.


Artifacts and Audit Outputs
The pipelines generate the following artifacts:



Artifact
Source Pipeline
Purpose




Terraform plan files
Terraform workflows
Ensures apply uses the reviewed plan


Coverage XML
PR checks and application CI
Test coverage reporting


JUnit XML
PR checks and application CI
Unit test result reporting


Bandit JSON
PR checks and application CI
SAST reporting


Docker image digest JSON
Application CI
Image audit traceability


Combined audit bundle
Application CI
Consolidated image build audit record




Rollback Approach
Application rollback can be handled through GitOps by reverting the Kubernetes manifest change to a previous image SHA and allowing Argo CD to reconcile the application.
Infrastructure rollback should be handled by reverting Terraform changes in Git and applying the corrected Terraform plan.
For destructive rollback or teardown, the manual destroy workflow should be used only after confirming the target environment and resource scope.
