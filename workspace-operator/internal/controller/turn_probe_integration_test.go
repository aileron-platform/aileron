package controller

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"net"
	"os"
	"strings"
	"testing"
	"time"

	"github.com/pion/logging"
	"github.com/pion/turn/v4"
)

func TestTURNProbeAllocatesRelayAndCompletesRoundTrip(t *testing.T) {
	endpoint := os.Getenv("TURN_INTEGRATION_ENDPOINT")
	if endpoint == "" {
		t.Skip("TURN_INTEGRATION_ENDPOINT is not configured")
	}
	sharedSecret := readTURNIntegrationSharedSecret(t)
	if sharedSecret == "" {
		t.Skip("TURN integration shared secret file is not configured")
	}
	username, credential := issueTURNRESTCredential(
		time.Now(),
		30,
		sharedSecret,
		"integration-probe",
	)
	deadline := time.Now().Add(20 * time.Second)
	var lastErr error
	for time.Now().Before(deadline) {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		relayAddress, err := probeTURNEndpoint(ctx, endpoint, username, credential)
		cancel()
		if err == nil && relayAddress != "" {
			return
		}
		lastErr = err
		time.Sleep(500 * time.Millisecond)
	}
	t.Fatalf("authenticated TURN allocation and relay round trip failed: %v", lastErr)
}

func TestTURNProbeAllocationSurvivesCredentialExpiry(t *testing.T) {
	endpoint := os.Getenv("TURN_INTEGRATION_ENDPOINT")
	sharedSecret := readTURNIntegrationSharedSecret(t)
	if endpoint == "" || sharedSecret == "" {
		t.Skip("TURN REST integration environment is not configured")
	}
	username, credential := issueTURNRESTCredential(
		time.Now(),
		3,
		sharedSecret,
		"expiry-probe",
	)
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()

	client, relayConn, mappedAddress := allocateIntegrationRelay(
		t,
		ctx,
		endpoint,
		username,
		credential,
	)
	defer client.Close()
	defer relayConn.Close()

	assertIntegrationRelayRoundTrip(t, ctx, relayConn, mappedAddress)
	time.Sleep(8 * time.Second)
	assertIntegrationRelayRoundTrip(t, ctx, relayConn, mappedAddress)
}

func readTURNIntegrationSharedSecret(t *testing.T) string {
	t.Helper()
	path := os.Getenv("TURN_INTEGRATION_SHARED_SECRET_FILE")
	if path == "" {
		return ""
	}
	value, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read TURN integration shared secret file: %v", err)
	}
	return strings.TrimSpace(string(value))
}

func allocateIntegrationRelay(
	t *testing.T,
	ctx context.Context,
	endpoint string,
	username string,
	credential string,
) (*turn.Client, net.PacketConn, net.Addr) {
	t.Helper()
	server, ok := parseTURNServerAddress(endpoint)
	hasUDP := false
	for _, protocol := range server.protocols {
		hasUDP = hasUDP || protocol == "UDP"
	}
	if !ok || !hasUDP {
		t.Fatalf("integration endpoint must support UDP TURN: %q", endpoint)
	}
	packetConn, err := net.ListenPacket("udp4", "0.0.0.0:0")
	if err != nil {
		t.Fatalf("listen for TURN integration test: %v", err)
	}
	loggerFactory := logging.NewDefaultLoggerFactory()
	loggerFactory.DefaultLogLevel = logging.LogLevelDisabled
	client, err := turn.NewClient(&turn.ClientConfig{
		STUNServerAddr: net.JoinHostPort(server.host, server.port),
		TURNServerAddr: net.JoinHostPort(server.host, server.port),
		Conn:           packetConn,
		Username:       username,
		Password:       credential,
		LoggerFactory:  loggerFactory,
	})
	if err != nil {
		packetConn.Close()
		t.Fatalf("create TURN integration client: %v", err)
	}
	if err := client.Listen(); err != nil {
		client.Close()
		t.Fatalf("start TURN integration client: %v", err)
	}
	relayConn, err := client.Allocate()
	if err != nil {
		client.Close()
		t.Fatalf("allocate TURN integration relay: %v", err)
	}
	mappedAddress, err := client.SendBindingRequest()
	if err != nil {
		relayConn.Close()
		client.Close()
		t.Fatalf("resolve mapped integration address: %v", err)
	}
	if deadline, ok := ctx.Deadline(); ok {
		if err := relayConn.SetDeadline(deadline); err != nil {
			relayConn.Close()
			client.Close()
			t.Fatalf("set TURN integration deadline: %v", err)
		}
	}
	return client, relayConn, mappedAddress
}

func assertIntegrationRelayRoundTrip(
	t *testing.T,
	ctx context.Context,
	relayConn net.PacketConn,
	mappedAddress net.Addr,
) {
	t.Helper()
	if _, err := relayConn.WriteTo([]byte("permission"), mappedAddress); err != nil {
		t.Fatalf("create integration relay permission: %v", err)
	}
	echoConn, err := net.ListenPacket("udp4", "0.0.0.0:0")
	if err != nil {
		t.Fatalf("listen for integration relay echo: %v", err)
	}
	defer echoConn.Close()
	if deadline, ok := ctx.Deadline(); ok {
		if err := echoConn.SetDeadline(deadline); err != nil {
			t.Fatalf("set integration echo deadline: %v", err)
		}
	}

	relayResult := make(chan error, 1)
	go func() {
		buffer := make([]byte, 128)
		count, source, readErr := relayConn.ReadFrom(buffer)
		if readErr == nil {
			_, readErr = relayConn.WriteTo(buffer[:count], source)
		}
		relayResult <- readErr
	}()
	nonceBytes := make([]byte, 16)
	if _, err := rand.Read(nonceBytes); err != nil {
		t.Fatalf("generate integration nonce: %v", err)
	}
	nonce := hex.EncodeToString(nonceBytes)
	if _, err := echoConn.WriteTo([]byte(nonce), relayConn.LocalAddr()); err != nil {
		t.Fatalf("send integration echo: %v", err)
	}
	buffer := make([]byte, 128)
	count, _, err := echoConn.ReadFrom(buffer)
	if err != nil {
		t.Fatalf("read integration echo: %v", err)
	}
	if err := <-relayResult; err != nil {
		t.Fatalf("relay integration echo: %v", err)
	}
	if got := string(buffer[:count]); got != nonce {
		t.Fatalf("TURN relay returned %q, want %q", got, nonce)
	}
}
