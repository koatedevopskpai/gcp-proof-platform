# Blog Topic Backlog — 200 Deeply Technical GCP Platform/DevOps Posts

Editorial backlog for the personal engineering blog (Astro + Firebase Hosting).

**Style/format (adopted from the Qiita "Cloud Run SLO monitoring with Terraform" model):**
one concrete technique per post, code-first (Terraform / YAML / shell), sections
`Overview → Steps → Extras → Links`, short and copy-pasteable. Each post should ship
working code and, where possible, tie back to a real workload in this repo.

Legend: `[ ]` not started · `[~]` drafting · `[x]` published

---

## Terraform & IaC

- [ ] 1. Structuring a GCP Terraform repo: environments, modules, remote state on GCS
- [ ] 2. Terraform state locking on GCS and recovering a corrupted state
- [ ] 3. `default_labels` as a FinOps taxonomy applied to every GCP resource
- [ ] 4. `for_each` vs `count`: safe refactors in GCP Terraform modules
- [ ] 5. Reusable Terraform modules for Cloud Run services
- [ ] 6. Drift detection with `terraform plan` in CI plus policy gates
- [ ] 7. Importing live GCP resources into Terraform without downtime
- [ ] 8. Workspaces vs directory-per-environment on GCP: tradeoffs
- [ ] 9. Gating Terraform with `validate`, `tflint`, and Checkov in CI
- [ ] 10. Provider version pinning and the GCS lockfile workflow
- [ ] 11. Bootstrapping GCP Terraform from `gcloud` output and `terraform import`
- [ ] 12. `moved` blocks: renaming resources without destroying infrastructure

## Compute Engine

- [ ] 13. Private VM with a metadata startup script on a hardened custom VPC
- [ ] 14. Managed Instance Groups with autoscaling and health checks
- [ ] 15. Rolling updates for a VM MIG behind an external HTTPS LB
- [ ] 16. Secure secret injection via metadata without key files
- [ ] 17. Persistent disk snapshots and snapshot schedules for backups
- [ ] 18. Spot VMs and graceful draining of preemptible workloads
- [ ] 19. Building a custom OS image with Packer for GCP VMs
- [ ] 20. Shielded VMs, vTPM, and integrity monitoring in Terraform
- [ ] 21. Debugging VMs via the serial console and IAP SSH
- [ ] 22. Automated rightsizing from the Recommender API
- [ ] 23. Idempotent startup scripts that are safe to re-run
- [ ] 24. Committed use discounts for always-on VMs

## Cloud Run

- [ ] 25. Cloud Run SLO monitoring with Terraform (canonical first post)
- [ ] 26. Multi-window multi-burn-rate SLO alerts for Cloud Run
- [ ] 27. CPU allocation: always-allocated vs request-based and cold starts
- [ ] 28. Min/max instances and concurrency tuning for latency SLOs
- [ ] 29. Canary and gradual rollouts with traffic splitting in Terraform
- [ ] 30. Direct VPC egress and Serverless VPC Access connectors
- [ ] 31. Cloud Run jobs vs services for batch and MLOps workloads
- [ ] 32. Distroless containers and non-root execution on Cloud Run
- [ ] 33. Domain mapping and managed TLS for custom domains
- [ ] 34. Cloud Run + Cloud SQL connection pooling with the Auth Proxy
- [ ] 35. Startup CPU boost and startup/liveness probes
- [ ] 36. Per-revision env vars and Secret Manager references
- [ ] 37. Serverless GPU on Cloud Run: when it's worth it
- [ ] 38. Cloud Run functions and 2nd-gen vs Cloud Functions

## GKE / Kubernetes / Helm

- [ ] 39. A cost-gated ephemeral GKE Autopilot cluster in Terraform
- [ ] 40. Helm charts for a multi-service platform with per-service values
- [ ] 41. GKE Gateway API vs Ingress: migrating a multi-service platform
- [ ] 42. Workload Identity on GKE (KSA ↔ GSA) without key files
- [ ] 43. Cluster autoscaling and node auto-provisioning economics
- [ ] 44. Binary Authorization: signing and admitting only approved images
- [ ] 45. Pod Security Admission enforcing `restricted` per namespace
- [ ] 46. Network policy with dataplane v2 for east-west zero trust
- [ ] 47. HPA and VPA with SLO-aware limits
- [ ] 48. GKE cost allocation by namespace/label via BigQuery billing export
- [ ] 49. Blue/green on GKE with Gateway API
- [ ] 50. KEDA autoscaling on Pub/Sub backlog
- [ ] 51. Persistent storage on GKE: Filestore, Hyperdisk, CSI drivers
- [ ] 52. Node upgrades: surge settings and maintenance windows
- [ ] 53. Multi-tenant GKE with namespaces, quotas, and HNC
- [ ] 54. Debugging CrashLoopBackOff and OOMKilled with Cloud Logging

## Networking

- [ ] 55. Hardened custom VPC with private Google access
- [ ] 56. Cloud NAT economics: when NAT breaks a $20 budget
- [ ] 57. Private Service Connect to Google APIs and producer services
- [ ] 58. Global external HTTPS LB with managed certificates
- [ ] 59. Internal load balancing for multi-tier applications
- [ ] 60. Cloud DNS private zones, peering, and split-horizon DNS
- [ ] 61. Cloud Armor WAF rules and edge rate limiting
- [ ] 62. VPC peering vs Shared VPC for org scale
- [ ] 63. Hybrid connectivity: HA VPN vs Dedicated/Partner Interconnect
- [ ] 64. Premium vs Standard network tiers for cost and latency
- [ ] 65. Firewall policies, hierarchical rules, target service accounts
- [ ] 66. Flow and firewall logs to BigQuery for forensics
- [ ] 67. Serverless VPC Access sizing and throughput math
- [ ] 68. Custom static routes and next-hop optimization
- [ ] 69. MTU/MSS tuning for GKE overlay networks
- [ ] 70. Multi-region load balancing and health-check failover

## Identity & Security

- [ ] 71. Workload Identity Federation for keyless GitHub Actions CI
- [ ] 72. Least-privilege service accounts with custom roles
- [ ] 73. IAM conditions for time-bound, resource-scoped access
- [ ] 74. Org policies restricting locations, services, and public IPs
- [ ] 75. VPC Service Controls perimeters and what breaks when enabled
- [ ] 76. Secret Manager rotation, versions, and `ignore_changes`
- [ ] 77. Cloud KMS envelope encryption and CMEK
- [ ] 78. Programmatic removal of unused permissions via IAM Recommender
- [ ] 79. Service account impersonation chains and delegation
- [ ] 80. Enforcing `iam.disableServiceAccountKeyCreation` in Terraform
- [ ] 81. Cloud Identity groups as IAM members at scale
- [ ] 82. Access Transparency and Access Approval
- [ ] 83. Binary Authorization and SLSA provenance for supply chain
- [ ] 84. SCC findings → Pub/Sub → auto-remediation
- [ ] 85. Detecting and remediating leaked service-account keys
- [ ] 86. CIS hardening for Container-Optimized OS
- [ ] 87. Certificate Authority Service for internal mTLS PKI
- [ ] 88. Principal Access Boundary (PAB) policies in GCP

## Observability & SRE

- [ ] 89. Production multi-window alerting from a single SLO
- [ ] 90. User-centric vs resource-centric SLIs from logs
- [ ] 91. Error-budget policies and release freezes
- [ ] 92. Log-based and distribution metrics from structured logs
- [ ] 93. Distributed tracing with Cloud Trace and OpenTelemetry
- [ ] 94. Golden-signals dashboards via the Monitoring dashboard API
- [ ] 95. Burn-rate alerts to Slack without hardcoding tokens
- [ ] 96. Log buckets, exclusion filters, and logging cost control
- [ ] 97. Log sink to BigQuery with partitioned tables
- [ ] 98. Uptime checks, private checks, and cert-expiry alerts
- [ ] 99. MQL vs PromQL on Managed Service for Prometheus
- [ ] 100. Synthetic monitoring with Cloud Run and Scheduler
- [ ] 101. Correlating Cloud Run revisions with error rates
- [ ] 102. Runbooks-as-code: linking alert policies to docs
- [ ] 103. Reducing alert noise with multi-condition policies
- [ ] 104. Version-controlling reliability: SLOs in Terraform

## CI/CD & DevSecOps

- [ ] 105. A DevSecOps Cloud Build pipeline: build → scan → SBOM → gate
- [ ] 106. Checkov policy-as-code gating Terraform
- [ ] 107. Trivy image scanning with Artifact Registry auth
- [ ] 108. Generating and storing SPDX SBOMs per build
- [ ] 109. SLSA provenance and artifact attestation with Cloud Build
- [ ] 110. Workload Identity Federation: GitHub Actions → GCP keyless
- [ ] 111. Cloud Deploy pipelines and release approvals
- [ ] 112. Canary deploys with Cloud Deploy + Cloud Run
- [ ] 113. Environment promotion dev→staging→prod with Cloud Deploy
- [ ] 114. Reusable Cloud Build steps with substitutions
- [ ] 115. Speeding up builds with Kaniko caching
- [ ] 116. Testing Python/Node/.NET in one pipeline
- [ ] 117. GitHub Actions vs Cloud Build for GCP deploys
- [ ] 118. Artifact Registry cleanup policies to cut storage cost
- [ ] 119. Policy enforcement with OPA/Conftest on Terraform
- [ ] 120. Secret scanning with gitleaks and trufflehog
- [ ] 121. Renovate/Dependabot for providers and base images
- [ ] 122. Rollback via revisions and `update-traffic`

## Data & Analytics

- [ ] 123. Loading MLOps eval results into BigQuery with a Cloud Run job
- [ ] 124. BigQuery partitioning and clustering for cheap queries
- [ ] 125. Scheduled queries vs orchestrators
- [ ] 126. Cost controls: `maximum_bytes_billed` and custom quotas
- [ ] 127. Streaming inserts vs Storage Write API vs Datastream
- [ ] 128. Pub/Sub → Dataflow → BigQuery exactly-once pipelines
- [ ] 129. Dataproc Serverless for Spark in Terraform
- [ ] 130. Materialized views and BI Engine under budget
- [ ] 131. External tables over GCS and BigLake governance
- [ ] 132. Column-level security and row-level access policies
- [ ] 133. Dataform/dbt for tested, versioned SQL
- [ ] 134. Bigtable schema design for time-series and IAM
- [ ] 135. Spanner: interleaved tables, autoscaling, multi-region
- [ ] 136. Firestore vs Cloud SQL for platform services
- [ ] 137. CDC from Cloud SQL with Datastream
- [ ] 138. A lakehouse on GCS + Iceberg + BigQuery
- [ ] 139. Data-freshness monitoring with custom metrics
- [ ] 140. Billing export to BigQuery for FinOps analytics

## Serverless & Workflows

- [ ] 141. Eventarc triggers for GCS and Audit Log events
- [ ] 142. Cloud Workflows orchestration with retries
- [ ] 143. Cloud Tasks for rate limiting and reliable delivery
- [ ] 144. Cloud Scheduler cron with OIDC-authenticated targets
- [ ] 145. Event-driven platform with Pub/Sub + Cloud Run
- [ ] 146. Dead-letter topics and retry/backoff design
- [ ] 147. Pub/Sub ordering keys and exactly-once delivery
- [ ] 148. Idempotency patterns for at-least-once delivery
- [ ] 149. Cloud Functions 2nd gen vs Cloud Run migration
- [ ] 150. Workflows callbacks for long-running jobs
- [ ] 151. Fan-out/fan-in with Pub/Sub and Cloud Run jobs
- [ ] 152. Saga orchestration for a multi-service platform

## Storage & Databases

- [ ] 153. GCS lifecycle rules, Autoclass, and storage classes
- [ ] 154. Object versioning, retention locks, and soft delete
- [ ] 155. Cloud Storage FUSE for GKE workloads
- [ ] 156. Signed URLs and IAM conditions for object access
- [ ] 157. Cloud SQL HA, read replicas, and failover drills
- [ ] 158. Cloud SQL Auth Proxy and private-IP-only connectivity
- [ ] 159. AlloyDB for Postgres: when it beats Cloud SQL
- [ ] 160. Memorystore for caching and rate limiting
- [ ] 161. Backup and tested restore for Cloud SQL/AlloyDB
- [ ] 162. DB migrations in CI/CD on Cloud Run jobs
- [ ] 163. Cross-region data residency with Spanner/BigQuery
- [ ] 164. Egress avoidance through same-region data gravity

## FinOps & Cost Engineering

- [ ] 165. Enforcing a $20/month label-scoped budget
- [ ] 166. Cost guardrails: budget → Pub/Sub → automatic shutdown
- [ ] 167. Committed and sustained-use discounts on GCE
- [ ] 168. Cost attribution with labels + Looker Studio
- [ ] 169. Automated rightsizing from the Recommender API
- [ ] 170. Spot VMs: the reliability vs cost tradeoff
- [ ] 171. Storage cost optimization and AR cleanup
- [ ] 172. Network egress optimization for Cloud Run and GCS
- [ ] 173. Showback/chargeback dashboards per team label
- [ ] 174. Cost anomaly detection with Cloud Monitoring
- [ ] 175. The real cost of NAT, load balancers, and GKE fees
- [ ] 176. Idle-resource detection and auto-cleanup

## Platform Engineering / IDP

- [ ] 177. Crossplane vs Terraform vs Config Connector on GCP
- [ ] 178. Config Connector: GCP resources as Kubernetes CRDs
- [ ] 179. An IDP with golden-path service templates
- [ ] 180. Backstage with GCP plugins for catalog + cost
- [ ] 181. Self-service environments via Terraform + WIF
- [ ] 182. OPA Gatekeeper on GKE and Conftest on Terraform
- [ ] 183. Multi-tenancy across projects and folders
- [ ] 184. A paved road: scaffold → CI → CD → SLO
- [ ] 185. Environment parity with modules and workspaces
- [ ] 186. Per-PR preview environments
- [ ] 187. Exposing platform APIs with Cloud Endpoints/Apigee
- [ ] 188. DORA metrics and platform scorecards on GCP

## MLOps & AI on GCP

- [ ] 189. Vertex AI Pipelines (KFP) for reproducible ML
- [ ] 190. Model registry and eval gate with BigQuery + Cloud Run
- [ ] 191. Vertex AI Matching Engine vs pgvector for vector search
- [ ] 192. RAG on GCP under budget: Cloud Run + pgvector
- [ ] 193. Vertex AI Model Monitoring for drift
- [ ] 194. Eval-score deployment gates in CI/CD
- [ ] 195. Vertex AI Feature Store vs BigQuery features
- [ ] 196. Batch prediction with Vertex AI and Cloud Run jobs
- [ ] 197. Open models on Cloud Run GPU vs Vertex endpoints
- [ ] 198. Cost-aware LLM inference: caching, batching, quotas
- [ ] 199. End-to-end MLOps: data → train → eval → deploy → monitor
- [ ] 200. AI security: prompt-injection defense and output filtering
