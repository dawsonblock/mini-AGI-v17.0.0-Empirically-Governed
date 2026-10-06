# RC14.2 Release Notes

RC14.2 closes two remaining trust seams from RC14.1: hidden-task service authorization and qualification evidence derivation.

The FreshTask daemon now distinguishes an evaluator capability from an administrator capability. Evaluator code can receive a one-shot task through a lease but cannot provision hidden tasks or reveal post-consumption commitments. This is an application-layer authorization boundary in addition to Unix socket permissions and encrypted-at-rest storage. A true secrecy boundary still requires the daemon, token files, database, and AES key to be inaccessible to the research process at the OS/service-principal layer.

Qualification is no longer based on caller-supplied pass booleans. The falsification store persists the exact run, and `QualificationEngineRC14` reconstructs mandatory class outcomes, pass rate, fresh OOD/hidden-task evidence, and signed independent attestations. `QualificationRecordRC14` binds the resulting evidence artifact, and candidate-state verification rejects disagreements between claimed qualification flags and the derived evidence object.

Request-derived learning can carry the exact source request and source StateEpoch. The canonical governed registration path verifies both against the active pinned `ExecutionContext`. StateEpoch preparation also has a canonical candidate-derived path that reconstructs qualification, promotion decision, and promotion authorization from signed candidate history.

Portable native C++ was freshly rebuilt for RC14.2 with CUDA and Metal disabled and the 25-test CTest suite re-executed. Python authority/runtime/reference suites are also rerun on the exact RC14.2 release tree. See `VALIDATION_SUMMARY.md` and `RELEASE_VALIDATION.json` for the final counts and exclusions.
