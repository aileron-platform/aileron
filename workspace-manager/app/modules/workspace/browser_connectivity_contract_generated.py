# Generated Browser connectivity contract constants. DO NOT EDIT.

BROWSER_CONNECTIVITY_CONTRACT_VERSION = "browser-connectivity/v1"
CONNECTIVITY_STATES = frozenset(
    [
        "pending",
        "ready",
        "degraded",
        "not_ready",
        "unavailable",
    ]
)
CONNECTIVITY_ADMISSIONS = frozenset(
    [
        "allowed",
        "denied",
    ]
)
CONNECTIVITY_REASONS = frozenset(
    [
        "BrowserNotRunning",
        "BrowserConnectivityPending",
        "BrowserConnectivityReady",
        "TURNProfileUnavailable",
        "BackendEvidenceUnavailable",
        "BackendTURNPathNotReady",
        "FrontendTURNPathNotReady",
        "BrowserConnectivityContractRejected",
    ]
)
CONNECTIVITY_ERROR_CODES = frozenset(
    [
        "TURN_PROFILE_UNAVAILABLE",
        "BACKEND_EVIDENCE_UNAVAILABLE",
        "BACKEND_TURN_PATH_NOT_READY",
        "FRONTEND_TURN_PATH_NOT_READY",
        "BROWSER_CONNECTIVITY_CONTRACT_REJECTED",
    ]
)
EVIDENCE_OUTCOMES = frozenset(
    [
        "success",
        "failure",
    ]
)
