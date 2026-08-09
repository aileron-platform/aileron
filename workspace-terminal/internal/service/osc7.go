package service

import (
	"bytes"
	"net/url"
	"path"
	"strings"
)

const (
	osc7Prefix          = "\x1b]7;"
	maxOSC7PayloadBytes = 32 * 1024
)

type osc7Observer struct {
	pending []byte
}

func (o *osc7Observer) Observe(data []byte) (string, bool) {
	o.pending = append(o.pending, data...)

	var latest string
	found := false
	for {
		start := bytes.Index(o.pending, []byte(osc7Prefix))
		if start < 0 {
			o.pending = retainOSC7PrefixSuffix(o.pending)
			return latest, found
		}
		o.pending = o.pending[start+len(osc7Prefix):]

		end, terminatorLength := findOSCTerminator(o.pending)
		if end < 0 {
			if len(o.pending) > maxOSC7PayloadBytes {
				o.pending = nil
			}
			return latest, found
		}

		payload := string(o.pending[:end])
		o.pending = o.pending[end+terminatorLength:]
		if workingDirectory, ok := parseOSC7WorkingDirectory(payload); ok {
			latest = workingDirectory
			found = true
		}
	}
}

func findOSCTerminator(data []byte) (int, int) {
	bellIndex := bytes.IndexByte(data, '\a')
	stringTerminatorIndex := bytes.Index(data, []byte{'\x1b', '\\'})
	switch {
	case bellIndex >= 0 && (stringTerminatorIndex < 0 || bellIndex < stringTerminatorIndex):
		return bellIndex, 1
	case stringTerminatorIndex >= 0:
		return stringTerminatorIndex, 2
	default:
		return -1, 0
	}
}

func retainOSC7PrefixSuffix(data []byte) []byte {
	prefix := []byte(osc7Prefix)
	maxLength := min(len(data), len(prefix)-1)
	for length := maxLength; length > 0; length-- {
		if bytes.Equal(data[len(data)-length:], prefix[:length]) {
			return append([]byte(nil), data[len(data)-length:]...)
		}
	}
	return nil
}

func parseOSC7WorkingDirectory(payload string) (string, bool) {
	location, err := url.Parse(payload)
	if err != nil ||
		location.Scheme != "file" ||
		location.User != nil ||
		location.RawQuery != "" ||
		location.Fragment != "" {
		return "", false
	}

	workingDirectory, err := url.PathUnescape(location.EscapedPath())
	if err != nil || !strings.HasPrefix(workingDirectory, "/") {
		return "", false
	}
	return path.Clean(workingDirectory), true
}
