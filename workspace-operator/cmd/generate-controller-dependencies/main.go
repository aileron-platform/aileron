package main

import (
	"flag"
	"fmt"
	"os"

	controllerdependencies "workspace-operator/internal/controllerdependencies"
)

func main() {
	contractPath := flag.String("contract", "", "Path to the canonical controller dependency registry")
	goOutputPath := flag.String("go-out", "", "Path for the generated Go registry")
	helmOutputPath := flag.String("helm-out", "", "Path for the generated Helm RBAC helpers")
	flag.Parse()
	if *contractPath == "" || *goOutputPath == "" || *helmOutputPath == "" {
		fmt.Fprintln(os.Stderr, "contract, go-out, and helm-out are required")
		os.Exit(2)
	}

	registry, err := controllerdependencies.LoadRegistry(*contractPath)
	if err != nil {
		fail(err)
	}
	goArtifact, helmArtifact, err := controllerdependencies.GenerateArtifacts(registry)
	if err != nil {
		fail(err)
	}
	if err := os.WriteFile(*goOutputPath, goArtifact, 0o644); err != nil {
		fail(fmt.Errorf("write generated Go registry: %w", err))
	}
	if err := os.WriteFile(*helmOutputPath, helmArtifact, 0o644); err != nil {
		fail(fmt.Errorf("write generated Helm registry: %w", err))
	}
}

func fail(err error) {
	fmt.Fprintln(os.Stderr, err)
	os.Exit(1)
}
