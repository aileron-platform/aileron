package main

import (
	"flag"
	"os"
	"strings"

	"k8s.io/apimachinery/pkg/runtime"
	utilruntime "k8s.io/apimachinery/pkg/util/runtime"
	clientgoscheme "k8s.io/client-go/kubernetes/scheme"
	ctrl "sigs.k8s.io/controller-runtime"
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

	flag.StringVar(&metricsAddr, "metrics-bind-address", ":8080", "The address the metric endpoint binds to.")
	flag.StringVar(&probeAddr, "health-probe-bind-address", ":8081", "The address the probe endpoint binds to.")
	flag.BoolVar(&enableLeaderElection, "leader-elect", false, "Enable leader election for controller manager.")
	flag.StringVar(&configNamespace, "config-namespace", os.Getenv("POD_NAMESPACE"), "Namespace used to read operator configuration resources.")

	opts := zap.Options{
		Development: true,
	}
	opts.BindFlags(flag.CommandLine)
	flag.Parse()

	ctrl.SetLogger(zap.New(zap.UseFlagOptions(&opts)))

	scheme := runtime.NewScheme()
	utilruntime.Must(clientgoscheme.AddToScheme(scheme))
	utilruntime.Must(workspacev1alpha1.AddToScheme(scheme))

	managerOptions := ctrl.Options{
		Scheme:                 scheme,
		HealthProbeBindAddress: probeAddr,
		LeaderElection:         enableLeaderElection,
		LeaderElectionID:       "workspace-operator.platform.aileron.io",
	}

	if metricsAddr != "0" {
		managerOptions.Metrics.BindAddress = metricsAddr
	}

	mgr, err := ctrl.NewManager(ctrl.GetConfigOrDie(), managerOptions)
	if err != nil {
		ctrl.Log.WithName("setup").Error(err, "unable to start manager")
		os.Exit(1)
	}

	publicRouting, err := controller.LoadPublicRoutingConfigFromEnv()
	if err != nil {
		ctrl.Log.WithName("setup").Error(err, "invalid public routing configuration")
		os.Exit(1)
	}

	if err := (&controller.WorkspaceReconciler{
		Client:                     mgr.GetClient(),
		Scheme:                     mgr.GetScheme(),
		ConfigNamespace:            configNamespace,
		CiliumEnabled:              strings.EqualFold(os.Getenv("CILIUM_ENABLED"), "true"),
		FirewallDefaultsConfigName: os.Getenv("FIREWALL_DEFAULTS_CONFIGMAP_NAME"),
		PublicRouting:              publicRouting,
		ManagerURL:                 os.Getenv("PLATFORM_MANAGER_URL"),
		KeycloakURL:                os.Getenv("PLATFORM_KEYCLOAK_URL"),
		KeycloakRealm:              os.Getenv("PLATFORM_KEYCLOAK_REALM"),
		KeycloakClientID:           os.Getenv("PLATFORM_KEYCLOAK_CLIENT_ID"),
		KeycloakClientSecret:       os.Getenv("PLATFORM_KEYCLOAK_CLIENT_SECRET"),
		RedisURL:                   os.Getenv("PLATFORM_REDIS_URL"),
		DatabaseURL:                os.Getenv("PLATFORM_DATABASE_URL"),
		InternalAPIToken:           os.Getenv("PLATFORM_INTERNAL_API_TOKEN"),
		KnowledgeBasesPVCName:      os.Getenv("KNOWLEDGE_BASES_PVC_NAME"),
		TURNServerURL:              os.Getenv("TURN_SERVER_URL"),
		TURNServerFrontendURL:      os.Getenv("TURN_SERVER_FRONTEND_URL"),
		TURNServerExternalIP:       os.Getenv("TURN_SERVER_EXTERNAL_IP"),
		TURNServerUsername:         os.Getenv("TURN_SERVER_USERNAME"),
		TURNServerCredential:       os.Getenv("TURN_SERVER_CREDENTIAL"),
	}).SetupWithManager(mgr); err != nil {
		ctrl.Log.WithName("setup").Error(err, "unable to create controller", "controller", "Workspace")
		os.Exit(1)
	}

	if err := mgr.AddHealthzCheck("healthz", healthz.Ping); err != nil {
		ctrl.Log.WithName("setup").Error(err, "unable to set up health check")
		os.Exit(1)
	}
	if err := mgr.AddReadyzCheck("readyz", healthz.Ping); err != nil {
		ctrl.Log.WithName("setup").Error(err, "unable to set up ready check")
		os.Exit(1)
	}

	ctrl.Log.WithName("setup").Info("starting manager")
	if err := mgr.Start(ctrl.SetupSignalHandler()); err != nil {
		ctrl.Log.WithName("setup").Error(err, "problem running manager")
		os.Exit(1)
	}
}
