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