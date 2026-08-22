package main

import (
	"flag"
	"fmt"
	"os"

	workspaceserviceidentities "workspace-operator/internal/workspaceserviceidentities"
)

func main() {
	contractPath := flag.String("contract", "", "Path to the canonical Workspace Service identity registry")
	goOutputPath := flag.String("go-out", "", "Path for the generated Go definitions")
	pythonOutputPath := flag.String("python-out", "", "Path for the generated Python definitions")
	flag.Parse()
	if *contractPath == "" || *goOutputPath == "" || *pythonOutputPath == "" {
		fmt.Fprintln(os.Stderr, "contract, go-out, and python-out are required")
		os.Exit(2)
	}

	registry, err := workspaceserviceidentities.LoadRegistry(*contractPath)
	if err != nil {
		fail(err)
	}
	goArtifact, pythonArtifact, err := workspaceserviceidentities.GenerateArtifacts(registry)
	if err != nil {
		fail(err)
	}
	if err := os.WriteFile(*goOutputPath, goArtifact, 0o644); err != nil {
		fail(fmt.Errorf("write generated Go definitions: %w", err))
	}
	if err := os.WriteFile(*pythonOutputPath, pythonArtifact, 0o644); err != nil {
		fail(fmt.Errorf("write generated Python definitions: %w", err))
	}
}

func fail(err error) {
	fmt.Fprintln(os.Stderr, err)
	os.Exit(1)
}
