package main

import (
	"context"
	"crypto/tls"
	"crypto/x509"
	"flag"
	"fmt"
	"net/http"
	"os"
	"strings"
	"time"

	"k8s.io/apimachinery/pkg/runtime"
	utilruntime "k8s.io/apimachinery/pkg/util/runtime"
	clientgoscheme "k8s.io/client-go/kubernetes/scheme"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/cache"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/healthz"
	"sigs.k8s.io/controller-runtime/pkg/log/zap"

	workspacev1alpha1 "workspace-operator/api/v1alpha1"
	"workspace-operator/internal/controller"
)

func main() {
	var metricsAddr string
	var probeAddr string
	var enableLeaderElection bool
	var configNamespace string
	var mode string
	var attestorNodeName string
	var ciliumSocketPath string
	var attestorPollInterval time.Duration
	var firewallAttestationMaxAge time.Duration
	var connectivityProbeAddr string
	podNamespace, err := loadPodNamespace(os.Getenv)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}

	flag.StringVar(&metricsAddr, "metrics-bind-address", ":8080", "The address the metric endpoint binds to.")
	flag.StringVar(&probeAddr, "health-probe-bind-address", ":8081", "The address the probe endpoint binds to.")
	flag.BoolVar(&enableLeaderElection, "leader-elect", false, "Enable leader election for controller manager.")
	flag.StringVar(&configNamespace, "config-namespace", podNamespace, "Namespace used to read operator configuration resources.")
	flag.StringVar(&mode, "mode", "controller", "Process mode: controller, firewall-attestor, browser-connectivity-probe, connectivity-evidence-gateway, or connectivity-external-agent.")
	flag.StringVar(&connectivityProbeAddr, "connectivity-probe-bind-address", ":8082", "The address used to serve Browser connectivity evidence.")
	flag.StringVar(&attestorNodeName, "attestor-node-name", "", "Kubernetes node assigned to the firewall attestor.")
	flag.StringVar(&ciliumSocketPath, "cilium-socket-path", "/var/run/cilium/cilium.sock", "Cilium agent Unix socket path.")
	flag.DurationVar(&attestorPollInterval, "firewall-attestor-poll-interval", 5*time.Second, "Firewall attestor polling interval.")
	flag.DurationVar(&firewallAttestationMaxAge, "firewall-attestation-max-age", 30*time.Second, "Maximum accepted firewall attestation age.")

	opts := zap.Options{
		Development: true,
	}
	opts.BindFlags(flag.CommandLine)
	flag.Parse()

	ctrl.SetLogger(zap.New(zap.UseFlagOptions(&opts)))
	if mode == "browser-connectivity-probe" {
		if err := runBrowserConnectivityProbe(connectivityProbeAddr); err != nil {
			ctrl.Log.WithName("setup").Error(err, "browser connectivity probe stopped")
			os.Exit(1)
		}
		return
	}
	if mode == "connectivity-evidence-gateway" {
		if err := runConnectivityEvidenceGateway(connectivityProbeAddr); err != nil {
			ctrl.Log.WithName("setup").Error(err, "connectivity evidence gateway stopped")
			os.Exit(1)
		}
		return
	}
	if mode == "connectivity-external-agent" {
		if err := runConnectivityExternalAgent(); err != nil {
			ctrl.Log.WithName("setup").Error(err, "connectivity external agent stopped")
			os.Exit(1)
		}
		return
	}

	scheme := runtime.NewScheme()
	utilruntime.Must(clientgoscheme.AddToScheme(scheme))
	utilruntime.Must(workspacev1alpha1.AddToScheme(scheme))
	if mode == "firewall-attestor" {
		kubernetesClient, err := client.New(
			ctrl.GetConfigOrDie(),
			client.Options{Scheme: scheme},
		)
		if err != nil {
			ctrl.Log.WithName("setup").Error(err, "unable to create firewall attestor Kubernetes client")
			os.Exit(1)
		}
		attestor := &controller.FirewallAttestor{
			Client:       kubernetesClient,
			NodeName:     attestorNodeName,
			Namespace:    podNamespace,
			SocketPath:   ciliumSocketPath,
			PollInterval: attestorPollInterval,
			MaxAge:       firewallAttestationMaxAge,
		}
		ctrl.Log.WithName("setup").Info("starting firewall attestor", "node", attestorNodeName)
		if err := attestor.Run(ctrl.SetupSignalHandler()); err != nil {
			ctrl.Log.WithName("setup").Error(err, "firewall attestor stopped")
			os.Exit(1)
		}
		return
	}
	if mode != "controller" {
		ctrl.Log.WithName("setup").Error(
			fmt.Errorf("unsupported mode %q", mode),
			"invalid process mode",
		)
		os.Exit(1)
	}
	operatorConfig, err := loadOperatorConfiguration()
	if err != nil {
		ctrl.Log.WithName("setup").Error(err, "invalid operator configuration")
		os.Exit(1)
	}

	managerOptions, err := buildManagerOptions(
		scheme,
		metricsAddr,
		probeAddr,
		enableLeaderElection,
		podNamespace,
	)
	if err != nil {
		ctrl.Log.WithName("setup").Error(err, "invalid operator namespace configuration")
		os.Exit(1)
	}

	mgr, err := ctrl.NewManager(ctrl.GetConfigOrDie(), managerOptions)
	if err != nil {
		ctrl.Log.WithName("setup").Error(err, "unable to start manager")
		os.Exit(1)
	}

	storageClassNames := []string{
		operatorConfig.workspaceStorageClass,
		operatorConfig.runtimeHomeStorageClass,
	}
	controllerDependencies := controller.EnabledControllerDependencies(controller.DependencyOptions{
		CiliumEnabled:     operatorConfig.ciliumEnabled,
		StorageClassNames: storageClassNames,
	})
	dependencyContext, cancelDependencyValidation := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancelDependencyValidation()
	if err := controller.ValidateControllerDependencies(
		dependencyContext,
		mgr.GetAPIReader(),
		mgr.GetRESTMapper(),
		controllerDependencies,
		storageClassNames,
	); err != nil {
		ctrl.Log.WithName("setup").Error(err, "controller dependencies are unavailable")
		os.Exit(1)
	}
	if err := controller.RegisterControllerDependencyInformers(
		dependencyContext,
		mgr.GetCache(),
		controllerDependencies,
	); err != nil {
		ctrl.Log.WithName("setup").Error(err, "controller dependency cache wiring is unavailable")
		os.Exit(1)
	}
	if err := (&controller.WorkspaceReconciler{
		Client:                         mgr.GetClient(),
		APIReader:                      mgr.GetAPIReader(),
		Scheme:                         mgr.GetScheme(),
		ConfigNamespace:                configNamespace,
		CiliumEnabled:                  operatorConfig.ciliumEnabled,
		FirewallAttestationMaxAge:      firewallAttestationMaxAge,
		PlatformPublicOrigin:           operatorConfig.platformPublicOrigin,
		ManagerURL:                     operatorConfig.managerURL,
		KnowledgeBasesPVCName:          operatorConfig.knowledgeBasesPVCName,
		PlatformStorageGID:             operatorConfig.platformStorageGID,
		WorkspaceStorageClass:          operatorConfig.workspaceStorageClass,
		RuntimeHomeStorageClass:        operatorConfig.runtimeHomeStorageClass,
		RuntimeHomeAccessMode:          operatorConfig.runtimeHomeAccessMode,
		WorkloadImagePullSecrets:       operatorConfig.workloadImagePullSecrets,
		TURNProfile:                    operatorConfig.turnProfile,
		TURNICEServersSecretName:       operatorConfig.turnICEServersSecretName,
		TURNBackendSecretKey:           operatorConfig.turnBackendSecretKey,
		TURNFrontendSecretKey:          operatorConfig.turnFrontendSecretKey,
		TURNCredentialRevision:         operatorConfig.turnCredentialRevision,
		BrowserConnectivityProbeImage:  operatorConfig.browserConnectivityProbeImage,
		ConnectivityEvidenceGatewayURL: operatorConfig.connectivityEvidenceGatewayURL,
		ConnectivityInstallationID:     operatorConfig.connectivityInstallationID,
		ConnectivityEvidenceReader: &controller.HTTPBrowserConnectivityEvidenceReader{
			Client:        &http.Client{Timeout: 3 * time.Second},
			FrontendToken: operatorConfig.connectivityGatewayToken,
		},
		BrowserCredentialKeyring: operatorConfig.browserCredentialKeyring,
	}).SetupWithManager(mgr, controllerDependencies); err != nil {
		ctrl.Log.WithName("setup").Error(err, "unable to create controller", "controller", "Workspace")
		os.Exit(1)
	}

	if err := mgr.AddHealthzCheck("healthz", healthz.Ping); err != nil {
		ctrl.Log.WithName("setup").Error(err, "unable to set up health check")
		os.Exit(1)
	}
	if err := mgr.AddReadyzCheck(
		"controller-operational",
		controller.ControllerOperationalReadiness(mgr.GetCache(), nil),
	); err != nil {
		ctrl.Log.WithName("setup").Error(err, "unable to set up ready check")
		os.Exit(1)
	}

	ctrl.Log.WithName("setup").Info("starting manager")
	if err := mgr.Start(ctrl.SetupSignalHandler()); err != nil {
		ctrl.Log.WithName("setup").Error(err, "problem running manager")
		os.Exit(1)
	}
}

func runConnectivityEvidenceGateway(bindAddress string) error {
	configuration, err := loadConnectivityEvidenceGatewayConfiguration()
	if err != nil {
		return err
	}
	gateway, err := controller.NewConnectivityEvidenceGateway(
		configuration.turnProfile,
		configuration.installationID,
		configuration.credentialRevision,
		configuration.frontendProbeICEServersJSON,
		configuration.agentTokensJSON,
		configuration.internalToken,
		configuration.turnRESTSharedSecret,
	)
	if err != nil {
		return err
	}
	return serveConnectivityHTTP(
		ctrl.SetupSignalHandler(),
		bindAddress,
		gateway.Handler(),
		"connectivity-evidence-gateway",
	)
}

func runConnectivityExternalAgent() error {
	configuration, err := loadConnectivityExternalAgentConfiguration()
	if err != nil {
		return err
	}
	agent := &controller.ExternalConnectivityProbeAgent{
		GatewayURL:     configuration.gatewayURL,
		InstallationID: configuration.installationID,
		VantageID:      configuration.vantageID,
		Token:          configuration.token,
		Client:         configuration.httpClient,
	}
	ctx := ctrl.SetupSignalHandler()
	for {
		probeContext, cancel := context.WithTimeout(ctx, 12*time.Second)
		err := agent.RunOnce(probeContext)
		cancel()
		if err != nil {
			ctrl.Log.WithName("connectivity-external-agent").Error(err, "external TURN probe failed")
		}
		timer := time.NewTimer(controller.JitterDuration(configuration.interval))
		select {
		case <-ctx.Done():
			timer.Stop()
			return nil
		case <-timer.C:
		}
	}
}

func newExternalConnectivityAgentHTTPClient(caFile string) (*http.Client, error) {
	transport := http.DefaultTransport.(*http.Transport).Clone()
	tlsConfig := &tls.Config{MinVersion: tls.VersionTLS12}
	if caFile != "" {
		caPEM, err := os.ReadFile(caFile)
		if err != nil {
			return nil, fmt.Errorf("read CONNECTIVITY_AGENT_CA_FILE: %w", err)
		}
		roots, err := x509.SystemCertPool()
		if err != nil {
			return nil, fmt.Errorf("load system certificate pool: %w", err)
		}
		if !roots.AppendCertsFromPEM(caPEM) {
			return nil, fmt.Errorf("CONNECTIVITY_AGENT_CA_FILE contains no valid certificates")
		}
		tlsConfig.RootCAs = roots
	}
	transport.TLSClientConfig = tlsConfig
	return &http.Client{Transport: transport, Timeout: 15 * time.Second}, nil
}

func readRequiredSecretFile(pathEnvironmentName string, rawPath string) (string, error) {
	if rawPath == "" {
		return "", fmt.Errorf("%s must identify a readable secret file", pathEnvironmentName)
	}
	if rawPath != strings.TrimSpace(rawPath) {
		return "", fmt.Errorf("%s must not contain surrounding whitespace", pathEnvironmentName)
	}
	path := rawPath
	contents, err := os.ReadFile(path)
	if err != nil {
		return "", fmt.Errorf("read %s: %w", pathEnvironmentName, err)
	}
	value := strings.TrimSpace(string(contents))
	if value == "" {
		return "", fmt.Errorf("%s must identify a non-empty secret file", pathEnvironmentName)
	}
	return value, nil
}

func serveConnectivityHTTP(ctx context.Context, bindAddress string, handler http.Handler, component string) error {
	httpServer := &http.Server{
		Addr:              bindAddress,
		Handler:           handler,
		ReadHeaderTimeout: 5 * time.Second,
	}
	go func() {
		<-ctx.Done()
		shutdownContext, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		if shutdownErr := httpServer.Shutdown(shutdownContext); shutdownErr != nil {
			ctrl.Log.WithName(component).Error(shutdownErr, "unable to stop HTTP server")
		}
	}()
	ctrl.Log.WithName(component).Info("starting HTTP server", "address", bindAddress)
	if err := httpServer.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		return err
	}
	return nil
}

func runBrowserConnectivityProbe(bindAddress string) error {
	configuration, err := loadBrowserConnectivityProbeConfiguration()
	if err != nil {
		return err
	}
	probe, err := controller.NewTURNProbeServer(
		configuration.turnProfile,
		configuration.credentialRevision,
		configuration.backendICEServersJSON,
		configuration.turnRESTSharedSecret,
		configuration.probeIdentity,
		configuration.installationID,
	)
	if err != nil {
		return err
	}
	ctx := ctrl.SetupSignalHandler()
	go probe.Run(ctx)
	httpServer := &http.Server{
		Addr:              bindAddress,
		Handler:           probe.Handler(),
		ReadHeaderTimeout: 5 * time.Second,
	}
	go func() {
		<-ctx.Done()
		shutdownContext, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		if shutdownErr := httpServer.Shutdown(shutdownContext); shutdownErr != nil {
			ctrl.Log.WithName("browser-connectivity-probe").Error(shutdownErr, "unable to stop evidence server")
		}
	}()
	ctrl.Log.WithName("browser-connectivity-probe").Info("starting evidence server", "address", bindAddress)
	if err := httpServer.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		return err
	}
	return nil
}

func buildManagerOptions(
	scheme *runtime.Scheme,
	metricsAddr string,
	probeAddr string,
	enableLeaderElection bool,
	podNamespace string,
) (ctrl.Options, error) {
	podNamespace = strings.TrimSpace(podNamespace)
	if podNamespace == "" {
		return ctrl.Options{}, fmt.Errorf("POD_NAMESPACE is required")
	}

	managerOptions := ctrl.Options{
		Scheme: scheme,
		Cache: cache.Options{
			DefaultNamespaces: map[string]cache.Config{
				podNamespace: {},
			},
		},
		HealthProbeBindAddress: probeAddr,
		LeaderElection:         enableLeaderElection,
		LeaderElectionID:       "workspace-operator.platform.aileron.io",
	}
	if metricsAddr != "0" {
		managerOptions.Metrics.BindAddress = metricsAddr
	}

	return managerOptions, nil
}
