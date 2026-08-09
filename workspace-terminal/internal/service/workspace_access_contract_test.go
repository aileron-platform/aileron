package service

import (
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/stretchr/testify/require"
)

type executionGrantContractVectors struct {
	ValidationEpoch int64 `json:"validationEpoch"`
	ExpectedContext struct {
		Issuer                string `json:"issuer"`
		WorkspaceID           string `json:"workspaceId"`
		RuntimeInstanceID     string `json:"runtimeInstanceId"`
		RuntimeAccessRevision int64  `json:"runtimeAccessRevision"`
	} `json:"expectedContext"`
	VerificationCases []struct {
		Name           string                 `json:"name"`
		Consumer       string                 `json:"consumer"`
		Accepted       bool                   `json:"accepted"`
		RequiredAction string                 `json:"requiredAction"`
		Claims         map[string]interface{} `json:"claims"`
	} `json:"verificationCases"`
}

func loadExecutionGrantContractVectors(t *testing.T) executionGrantContractVectors {
	t.Helper()
	contractRoot := os.Getenv("EXECUTION_GRANT_CONTRACT_DIR")
	if contractRoot == "" {
		contractRoot = filepath.Join("..", "..", "..", "contracts", "workspace-execution-access")
	}
	content, err := os.ReadFile(filepath.Join(contractRoot, "conformance-vectors.json"))
	require.NoError(t, err)
	var vectors executionGrantContractVectors
	require.NoError(t, json.Unmarshal(content, &vectors))
	return vectors
}

func TestTerminalVerifierConformsToCanonicalExecutionGrantVectors(t *testing.T) {
	vectors := loadExecutionGrantContractVectors(t)
	now := time.Unix(vectors.ValidationEpoch, 0).UTC()
	key := newAssertionTestKey(t, "manager-v1")
	verifier, err := newLocalWorkspaceAccessVerifier(
		writeAssertionJWKS(t, key),
		vectors.ExpectedContext.Issuer,
		vectors.ExpectedContext.WorkspaceID,
		vectors.ExpectedContext.RuntimeInstanceID,
		vectors.ExpectedContext.RuntimeAccessRevision,
		func() time.Time { return now },
	)
	require.NoError(t, err)

	for _, testCase := range vectors.VerificationCases {
		if testCase.Consumer != "terminal" {
			continue
		}
		t.Run(testCase.Name, func(t *testing.T) {
			grant := signDrainAssertion(t, key, testCase.Claims)
			err := verifier.VerifyTerminalAccess(
				context.Background(),
				grant,
				vectors.ExpectedContext.WorkspaceID,
			)
			if testCase.Accepted {
				require.NoError(t, err)
				return
			}
			require.Error(t, err)
		})
	}
}
