package controller

import (
	"context"
	"errors"
	"net/http/httptest"
	"reflect"
	"testing"

	storagev1 "k8s.io/api/storage/v1"
	"k8s.io/apimachinery/pkg/api/meta"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/runtime/schema"
	"sigs.k8s.io/controller-runtime/pkg/cache"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/client/fake"

	controllerdependencies "workspace-operator/internal/controllerdependencies"
)

type cacheSyncStub bool

func (stub cacheSyncStub) WaitForCacheSync(context.Context) bool { return bool(stub) }

type informerRegistrarStub struct{ objects []client.Object }

func (stub *informerRegistrarStub) GetInformer(
	_ context.Context,
	object client.Object,
	_ ...cache.InformerGetOption,
) (cache.Informer, error) {
	stub.objects = append(stub.objects, object)
	return nil, nil
}

func TestEnabledControllerDependenciesExcludeDisabledCapabilities(t *testing.T) {
	dependencies := EnabledControllerDependencies(DependencyOptions{})
	identities := make([]string, 0, len(dependencies))
	for _, dependency := range dependencies {
		identities = append(identities, dependency.Identity)
	}
	want := []string{
		"core.persistent-volume-claims",
		"core.pods",
		"core.secrets",
		"core.service-accounts",
		"core.services",
		"workloads.deployments",
		"workspace.finalizers",
		"workspace.primary",
		"workspace.status",
	}
	if !reflect.DeepEqual(identities, want) {
		t.Fatalf("enabled identities = %#v, want %#v", identities, want)
	}
}

func TestEnabledControllerDependenciesIncludeConfiguredCapabilities(t *testing.T) {
	dependencies := EnabledControllerDependencies(DependencyOptions{
		CiliumEnabled:     true,
		StorageClassNames: []string{"workspace-data"},
	})
	if len(dependencies) != 12 {
		t.Fatalf("enabled dependency count = %d, want 12", len(dependencies))
	}
}

func TestNormalizeStorageClassNamesIsDeterministicAndUnique(t *testing.T) {
	got := normalizeStorageClassNames([]string{" runtime-home ", "workspace-data", "runtime-home", ""})
	want := []string{"runtime-home", "workspace-data"}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("dependencies = %#v, want %#v", got, want)
	}
}

func TestValidateControllerDependenciesUsesNamedDirectLookups(t *testing.T) {
	scheme := runtime.NewScheme()
	if err := storagev1.AddToScheme(scheme); err != nil {
		t.Fatalf("add storage scheme: %v", err)
	}
	reader := fake.NewClientBuilder().WithScheme(scheme).WithObjects(
		&storagev1.StorageClass{ObjectMeta: metav1.ObjectMeta{Name: "workspace-data"}},
	).Build()
	mapper := meta.NewDefaultRESTMapper([]schema.GroupVersion{storagev1.SchemeGroupVersion})
	mapper.Add(storagev1.SchemeGroupVersion.WithKind("StorageClass"), meta.RESTScopeRoot)
	allDependencies := EnabledControllerDependencies(DependencyOptions{
		StorageClassNames: []string{"workspace-data"},
	})
	dependencies := dependencyByIdentity(t, allDependencies, "storage.storage-classes")

	if err := ValidateControllerDependencies(
		context.Background(),
		reader,
		mapper,
		[]controllerdependencies.Dependency{dependencies},
		[]string{"workspace-data"},
	); err != nil {
		t.Fatalf("validate dependencies: %v", err)
	}
	if err := ValidateControllerDependencies(
		context.Background(),
		reader,
		mapper,
		[]controllerdependencies.Dependency{dependencies},
		[]string{"missing"},
	); err == nil {
		t.Fatal("missing direct lookup dependency was accepted")
	}
}

func TestValidateControllerDependenciesRejectsMissingDiscoveryAndWrongScope(t *testing.T) {
	allDependencies := EnabledControllerDependencies(DependencyOptions{
		StorageClassNames: []string{"workspace-data"},
	})
	dependency := dependencyByIdentity(t, allDependencies, "storage.storage-classes")
	dependencies := []controllerdependencies.Dependency{dependency}
	emptyMapper := meta.NewDefaultRESTMapper([]schema.GroupVersion{storagev1.SchemeGroupVersion})
	if err := ValidateControllerDependencies(
		context.Background(),
		fake.NewClientBuilder().Build(),
		emptyMapper,
		dependencies,
		[]string{"workspace-data"},
	); err == nil {
		t.Fatal("missing StorageClass discovery was accepted")
	}

	wrongScopeMapper := meta.NewDefaultRESTMapper([]schema.GroupVersion{storagev1.SchemeGroupVersion})
	wrongScopeMapper.Add(storagev1.SchemeGroupVersion.WithKind("StorageClass"), meta.RESTScopeNamespace)
	if err := ValidateControllerDependencies(
		context.Background(),
		fake.NewClientBuilder().Build(),
		wrongScopeMapper,
		dependencies,
		[]string{"workspace-data"},
	); err == nil {
		t.Fatal("namespaced StorageClass discovery was accepted")
	}
}

func dependencyByIdentity(
	t *testing.T,
	dependencies []controllerdependencies.Dependency,
	identity string,
) controllerdependencies.Dependency {
	t.Helper()
	for _, dependency := range dependencies {
		if dependency.Identity == identity {
			return dependency
		}
	}
	t.Fatalf("dependency %s was not enabled", identity)
	return controllerdependencies.Dependency{}
}

func TestControllerWiringPlanMatchesEnabledWatchedDependencies(t *testing.T) {
	dependencies := EnabledControllerDependencies(DependencyOptions{CiliumEnabled: true})
	plan, err := BuildControllerWiringPlan(dependencies)
	if err != nil {
		t.Fatalf("build wiring plan: %v", err)
	}
	want := []ControllerRegistration{
		{Identity: "workspace.primary", Registration: RegistrationPrimary, MapperIdentity: "primaryResource"},
		{Identity: "cilium.endpoints", Registration: RegistrationWatch, MapperIdentity: "ciliumEndpointToWorkspace"},
		{Identity: "cilium.network-policies", Registration: RegistrationOwn, MapperIdentity: "ownerReference"},
		{Identity: "core.persistent-volume-claims", Registration: RegistrationOwn, MapperIdentity: "ownerReference"},
		{Identity: "core.pods", Registration: RegistrationWatch, MapperIdentity: "managedPodToWorkspace"},
		{Identity: "core.service-accounts", Registration: RegistrationOwn, MapperIdentity: "ownerReference"},
		{Identity: "workloads.deployments", Registration: RegistrationOwn, MapperIdentity: "ownerReference"},
	}
	if !reflect.DeepEqual(plan, want) {
		t.Fatalf("wiring plan = %#v, want %#v", plan, want)
	}
}

func TestControllerOperationalReadinessRequiresPreflightAndCacheSync(t *testing.T) {
	request := httptest.NewRequest("GET", "/readyz", nil)
	if err := ControllerOperationalReadiness(cacheSyncStub(true), errors.New("discovery failed"))(request); err == nil {
		t.Fatal("failed dependency preflight was ready")
	}
	if err := ControllerOperationalReadiness(cacheSyncStub(false), nil)(request); err == nil {
		t.Fatal("unsynchronized dependency cache was ready")
	}
	if err := ControllerOperationalReadiness(cacheSyncStub(true), nil)(request); err != nil {
		t.Fatalf("ready dependency set was rejected: %v", err)
	}
}

func TestRegisterControllerDependencyInformersCoversEntireEnabledCache(t *testing.T) {
	registrar := &informerRegistrarStub{}
	dependencies := EnabledControllerDependencies(DependencyOptions{CiliumEnabled: true})
	if err := RegisterControllerDependencyInformers(context.Background(), registrar, dependencies); err != nil {
		t.Fatalf("register dependency informers: %v", err)
	}
	if len(registrar.objects) != 9 {
		t.Fatalf("registered informer count = %d, want 9", len(registrar.objects))
	}
}
