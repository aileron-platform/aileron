# workspace-operator

`workspace-operator` is the Kubernetes controller for the `Workspace` custom resource.

Current scope:

- register `platform.aileron.io/v1alpha1` `Workspace`
- watch `Workspace` resources
- perform the basic reconcile loop
- manage finalizers
- write back the minimum status fields

Planned additions:

- reconcile runtime, canvas, and browser Deployments
- reconcile Services and PVCs
- reconcile Cilium network policies
- write richer status information

## Local Development

```bash
go test ./...
make test-container
go run ./cmd/main.go
```
