package controller

import (
	"context"
	"fmt"
	"net/http"
	"sort"
	"strings"
	"time"

	appsv1 "k8s.io/api/apps/v1"
	corev1 "k8s.io/api/core/v1"
	storagev1 "k8s.io/api/storage/v1"
	"k8s.io/apimachinery/pkg/api/meta"
	"k8s.io/apimachinery/pkg/apis/meta/v1/unstructured"
	"k8s.io/apimachinery/pkg/runtime/schema"
	"k8s.io/apimachinery/pkg/types"
	"sigs.k8s.io/controller-runtime/pkg/cache"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/healthz"

	workspacev1alpha1 "workspace-operator/api/v1alpha1"
	controllerdependencies "workspace-operator/internal/controllerdependencies"
)

type DependencyOptions struct {
	CiliumEnabled     bool
	StorageClassNames []string
}

type Registration string

const (
	RegistrationPrimary Registration = "primary"
	RegistrationOwn     Registration = "own"
	RegistrationWatch   Registration = "watch"
)

type ControllerRegistration struct {
	Identity       string
	Registration   Registration
	MapperIdentity string
}

type CacheSyncer interface {
	WaitForCacheSync(context.Context) bool
}

type InformerRegistrar interface {
	GetInformer(context.Context, client.Object, ...cache.InformerGetOption) (cache.Informer, error)
}

func EnabledControllerDependencies(options DependencyOptions) []controllerdependencies.Dependency {
	storageClassesConfigured := len(normalizeStorageClassNames(options.StorageClassNames)) > 0
	dependencies := make([]controllerdependencies.Dependency, 0, len(canonicalControllerDependencies))
	for _, dependency := range canonicalControllerDependencies {
		enabled := false
		switch dependency.EnabledCondition {
		case controllerdependencies.ConditionAlways:
			enabled = true
		case controllerdependencies.ConditionCiliumEnabled:
			enabled = options.CiliumEnabled
		case controllerdependencies.ConditionStorageClassesConfigured:
			enabled = storageClassesConfigured
		}
		if enabled {
			dependencies = append(dependencies, dependency)
		}
	}
	return dependencies
}

func BuildControllerWiringPlan(dependencies []controllerdependencies.Dependency) ([]ControllerRegistration, error) {
	plan := make([]ControllerRegistration, 0, len(dependencies))
	var primary *ControllerRegistration
	for _, dependency := range dependencies {
		if _, err := dependencyGVK(dependency.TypedObject); err != nil {
			return nil, fmt.Errorf("dependency %s wiring is invalid: %w", dependency.Identity, err)
		}
		if dependency.AccessMode != controllerdependencies.AccessModeWatched {
			continue
		}
		registration := ControllerRegistration{
			Identity:       dependency.Identity,
			MapperIdentity: dependency.EventMapperIdentity,
		}
		switch dependency.EventMapperIdentity {
		case "primaryResource":
			registration.Registration = RegistrationPrimary
			if primary != nil {
				return nil, fmt.Errorf("multiple primary controller dependencies")
			}
			copy := registration
			primary = &copy
		case "ownerReference":
			registration.Registration = RegistrationOwn
			plan = append(plan, registration)
		case "managedPodToWorkspace", "ciliumEndpointToWorkspace":
			registration.Registration = RegistrationWatch
			plan = append(plan, registration)
		default:
			return nil, fmt.Errorf("dependency %s has unsupported event mapper %q", dependency.Identity, dependency.EventMapperIdentity)
		}
	}
	if primary == nil {
		return nil, fmt.Errorf("primary controller dependency is required")
	}
	return append([]ControllerRegistration{*primary}, plan...), nil
}

func ControllerOperationalReadiness(cacheSyncer CacheSyncer, preflightErr error) healthz.Checker {
	return func(request *http.Request) error {
		if preflightErr != nil {
			return fmt.Errorf("controller dependency preflight failed: %w", preflightErr)
		}
		if cacheSyncer == nil {
			return fmt.Errorf("controller dependency cache is required")
		}
		ctx, cancel := context.WithTimeout(request.Context(), 100*time.Millisecond)
		defer cancel()
		if !cacheSyncer.WaitForCacheSync(ctx) {
			return fmt.Errorf("enabled controller dependency cache is not synchronized")
		}
		return nil
	}
}

func RegisterControllerDependencyInformers(
	ctx context.Context,
	registrar InformerRegistrar,
	dependencies []controllerdependencies.Dependency,
) error {
	if registrar == nil {
		return fmt.Errorf("controller dependency informer registrar is required")
	}
	registered := map[schema.GroupVersionKind]struct{}{}
	for _, dependency := range dependencies {
		if dependency.AccessMode == controllerdependencies.AccessModeDirectLookup {
			continue
		}
		gvk, err := dependencyGVK(dependency.TypedObject)
		if err != nil {
			return fmt.Errorf("dependency %s informer wiring is invalid: %w", dependency.Identity, err)
		}
		if _, exists := registered[gvk]; exists {
			continue
		}
		object, err := controllerDependencyObject(dependency)
		if err != nil {
			return err
		}
		if _, err := registrar.GetInformer(ctx, object, cache.BlockUntilSynced(false)); err != nil {
			return fmt.Errorf("dependency %s informer registration failed: %w", dependency.Identity, err)
		}
		registered[gvk] = struct{}{}
	}
	return nil
}

func normalizeStorageClassNames(names []string) []string {
	unique := map[string]struct{}{}
	for _, name := range names {
		name = strings.TrimSpace(name)
		if name != "" {
			unique[name] = struct{}{}
		}
	}
	ordered := make([]string, 0, len(unique))
	for name := range unique {
		ordered = append(ordered, name)
	}
	sort.Strings(ordered)
	return ordered
}

func ValidateControllerDependencies(
	ctx context.Context,
	reader client.Reader,
	mapper meta.RESTMapper,
	dependencies []controllerdependencies.Dependency,
	storageClassNames []string,
) error {
	if mapper == nil {
		return fmt.Errorf("controller REST mapper is required")
	}
	for _, dependency := range dependencies {
		gvk, err := dependencyGVK(dependency.TypedObject)
		if err != nil {
			return fmt.Errorf("dependency %s wiring is invalid: %w", dependency.Identity, err)
		}
		mapping, err := mapper.RESTMapping(gvk.GroupKind(), gvk.Version)
		if err != nil {
			return fmt.Errorf("dependency %s discovery failed: %w", dependency.Identity, err)
		}
		resource := strings.SplitN(dependency.Resource, "/", 2)[0]
		if mapping.Resource.Resource != resource {
			return fmt.Errorf("dependency %s discovered resource %s, want %s", dependency.Identity, mapping.Resource.Resource, resource)
		}
		wantNamespaced := dependency.Scope == controllerdependencies.ScopeNamespaced
		isNamespaced := mapping.Scope.Name() == meta.RESTScopeNameNamespace
		if wantNamespaced != isNamespaced {
			return fmt.Errorf("dependency %s discovered scope %s, want %s", dependency.Identity, mapping.Scope.Name(), dependency.Scope)
		}
		if dependency.AccessMode == controllerdependencies.AccessModeDirectLookup {
			if err := probeDirectLookup(ctx, reader, dependency.ProbeIdentity, storageClassNames); err != nil {
				return fmt.Errorf("dependency %s probe failed: %w", dependency.Identity, err)
			}
		}
	}
	return nil
}

func probeDirectLookup(ctx context.Context, reader client.Reader, identity string, storageClassNames []string) error {
	if reader == nil {
		return fmt.Errorf("controller API reader is required")
	}
	if identity != "configuredStorageClasses" {
		return fmt.Errorf("unsupported direct lookup probe %q", identity)
	}
	for _, name := range normalizeStorageClassNames(storageClassNames) {
		if err := reader.Get(ctx, types.NamespacedName{Name: name}, &storagev1.StorageClass{}); err != nil {
			return fmt.Errorf("StorageClass %s is unavailable: %w", name, err)
		}
	}
	return nil
}

func dependencyGVK(typedObject string) (schema.GroupVersionKind, error) {
	switch typedObject {
	case "appsv1.Deployment":
		return appsv1.SchemeGroupVersion.WithKind("Deployment"), nil
	case "corev1.PersistentVolumeClaim":
		return corev1.SchemeGroupVersion.WithKind("PersistentVolumeClaim"), nil
	case "corev1.Pod":
		return corev1.SchemeGroupVersion.WithKind("Pod"), nil
	case "corev1.Secret":
		return corev1.SchemeGroupVersion.WithKind("Secret"), nil
	case "corev1.Service":
		return corev1.SchemeGroupVersion.WithKind("Service"), nil
	case "corev1.ServiceAccount":
		return corev1.SchemeGroupVersion.WithKind("ServiceAccount"), nil
	case "storagev1.StorageClass":
		return storagev1.SchemeGroupVersion.WithKind("StorageClass"), nil
	case "workspacev1alpha1.Workspace":
		return workspacev1alpha1.GroupVersion.WithKind("Workspace"), nil
	case "cilium.io/v2.CiliumEndpoint":
		return ciliumEndpointGVK, nil
	case "cilium.io/v2.CiliumNetworkPolicy":
		return ciliumNetworkPolicyGVK, nil
	default:
		return schema.GroupVersionKind{}, fmt.Errorf("unsupported typed object %q", typedObject)
	}
}

func controllerDependencyObject(dependency controllerdependencies.Dependency) (client.Object, error) {
	switch dependency.TypedObject {
	case "workspacev1alpha1.Workspace":
		return &workspacev1alpha1.Workspace{}, nil
	case "appsv1.Deployment":
		return &appsv1.Deployment{}, nil
	case "corev1.PersistentVolumeClaim":
		return &corev1.PersistentVolumeClaim{}, nil
	case "corev1.Pod":
		return &corev1.Pod{}, nil
	case "corev1.Secret":
		return &corev1.Secret{}, nil
	case "corev1.Service":
		return &corev1.Service{}, nil
	case "corev1.ServiceAccount":
		return &corev1.ServiceAccount{}, nil
	case "cilium.io/v2.CiliumEndpoint", "cilium.io/v2.CiliumNetworkPolicy":
		object := &unstructured.Unstructured{}
		gvk, err := dependencyGVK(dependency.TypedObject)
		if err != nil {
			return nil, err
		}
		object.SetGroupVersionKind(gvk)
		return object, nil
	default:
		return nil, fmt.Errorf("dependency %s cannot register typed object %s", dependency.Identity, dependency.TypedObject)
	}
}
