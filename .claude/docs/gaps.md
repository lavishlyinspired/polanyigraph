The plan is comprehensive (2401 lines) covering architecture, skills, memory, and implementation phases. Here's my review with gaps and recommendations:
Critical Gaps (High Priority)
1. Current State / Progress Tracking
- The plan has 12 phases but no mechanism to track what's DONE vs TODO
- MVP_PLAN.md tracks this but isn't referenced in the full plan
- Add: Section "Implementation Status" linking to MVP_PLAN.md, with a matrix of phase completion
2. Dependency Graph Between Phases
- Phases are listed linearly but dependencies aren't explicit
- Example: Phase 6 (LangGraph) depends on Phase 1-5; Phase 9 (Frontend) depends on Phase 7 (Extraction)
- Add: DAG diagram showing phase dependencies
3. Risk Register
- No risks or mitigation strategies documented
- Key risks: LLM API instability (glm-5.2 hang), Neo4j memory limits, extraction quality variance
- Add: Section with risk matrix (probability × impact × mitigation)
4. Testing Strategy
- TDD is mentioned but no comprehensive testing architecture
- Missing: integration tests, E2E tests, load tests, chaos tests
- Add: Section "Testing Strategy" with unit/integration/E2E/load test plans
Important Gaps (Medium Priority)
5. Error Handling & Resilience
- No section on failure modes (LLM timeout, Neo4j down, extraction quality low)
- §20.6 mentions "no crash" but no systematic resilience pattern
- Add: Section with circuit breakers, retries, fallbacks, graceful degradation
6. Monitoring & Observability
- Langfuse mentioned briefly in §2.9.8 but no dedicated section
- Missing: metrics (latency, throughput, error rates), logging, alerting
- Add: Section "Observability" with metrics, logs, traces, dashboards
7. Security
- No authentication, authorization, or data privacy considerations
- Missing: API key rotation, RBAC, PII handling in extracted text
- Add: Section "Security" with auth, authz, data privacy, secret management
8. Cost Estimation
- No LLM call cost analysis (tokens × price per 1K)
- Missing: infrastructure cost (Neo4j, Redis, PostgreSQL), operational cost
- Add: Section "Cost Model" with per-operation cost breakdown
Minor Gaps (Lower Priority)
9. Migration Strategy
- How to migrate from MVP → v1 (schema changes, data migration)
- Add: Brief section on migration path
10. API Versioning
- No versioning strategy for REST endpoints
- Add: Note on versioning approach (URL path vs header)
11. Data Retention & Cleanup
- §4.8 mentions "daily compaction" but no formal policy
- Add: Data retention policy (30-day, 90-day, 1-year windows)
12. Development Workflow
- No CI/CD pipeline details (lint, typecheck, test, build, deploy)
- Add: Section on development workflow and quality gates
13. Incident Response
- No incident management process
- Add: Brief section on escalation, rollback, communication
14. Performance Requirements
- No latency/throughput targets defined
- §4.9 mentions "18ms p50" but no formal SLOs
- Add: Section with latency targets per operation
15. Audit Trail
- No audit logging requirements (who did what, when)
- Add: Note on audit logging for compliance
Structural Issues
16. Decision Records (§18, §19, §20)
- These are valuable but scattered at the end
- Recommendation: Move to a dedicated "Decision Log" section or integrate into relevant architecture sections
17. §4 Superseded Content
- §4 is marked superseded by §20 but kept for history
- Recommendation: Add clear "HISTORICAL - DO NOT IMPLEMENT" header or remove entirely
18. Phase Placement Mismatch
- §18.3 places skill graph work in Phase 3/4, but Phase 3 is "Memory Layer" and Phase 4 is "MCP Layer"
- Clarify: Which phase actually implements the skill graph schema?
19. Missing Cross-References
- §19.5 references "§7.3 (already speced)" but doesn't link to the actual implementation
- §20.3 references "services/graph_service.upsert_entity" but no file path
- Add: File path references for implemented components
20. Incomplete Phase Definitions
- Phase 11 is "Polish + Deploy" but very vague
- Expand: Define specific polish items (a11y, i18n, responsive, browser support)
Recommended Additions (By Priority)
#	Section	Rationale
1	Implementation Status Matrix	Track what's DONE vs TODO
2	Phase Dependency DAG	Visualize blocking relationships
3	Risk Register	Mitigate known risks early
4	Testing Strategy	Ensure quality at each phase
5	Error Handling & Resilience	Prevent production failures
6	Monitoring & Observability	Debug issues in production
7	Security	Protect against attacks
8	Cost Model	Understand operational costs
9	Performance Requirements	Define SLOs for SLAs
10	Data Retention Policy	Comply with regulations
Immediate Actions
1. Add §1 Implementation Status Matrix — reference MVP_PLAN.md phases, mark DONE/TODO
2. Add §2 Phase Dependency DAG — show Phase 0→1→2→...→11 blocking relationships
3. Add §3 Risk Register — document LLM instability, Neo4j memory, extraction quality risks
4. Add §4 Testing Strategy — unit/integration/E2E/load test plans
5. Clean up §4 — add "HISTORICAL" header or remove superseded content
6. Integrate §18/§19/§20 — move decision records to dedicated section or inline