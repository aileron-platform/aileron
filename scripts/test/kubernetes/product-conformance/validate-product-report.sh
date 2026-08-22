#!/bin/sh

set -eu

report="${1:?product conformance report path is required}"

jq -e '
  .schemaVersion == 1
  and .result == "passed"
  and (
    (.capabilities | keys | sort)
    == ([
      "managerApiLifecycle",
      "externalOidcAuthorizationCodeJit",
      "durableJobs",
      "rapidConsecutiveMutations",
      "reconcileFailureRetry",
      "startStopRestart",
      "errorRecovery",
      "stoppedWorkspace",
      "actionGate",
      "signedDrain",
      "forcedTerminationProof",
      "oldConnectionRejection",
      "browserPairing"
    ] | sort)
  )
  and ([
    .capabilities[]
    | (
      .passed == true
      and (.failure == null)
      and (.evidence | type == "array")
      and (.evidence | length > 0)
      and ([
        .evidence[]
        | (
          (.kind | type == "string" and length > 0)
          and (.ref | type == "string" and length > 0)
          and (.assertion | type == "string" and length > 0)
          and has("observed")
          and (.observed != null)
        )
      ] | all)
    )
  ] | all)
' "${report}" >/dev/null
