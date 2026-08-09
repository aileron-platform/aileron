import { describe, expect, it } from 'vitest';
import { parseResourceError, parseResourceResult, toResourceList } from './resourceEnvelope';

describe('parseResourceError', () => {
  it('reads marketplace detail shape', () => {
    const err = {
      response: {
        data: {
          detail: {
            errorCode: 'marketplace.path.invalid',
            message: 'bad path',
            validationResults: [{ code: 'x' }],
          },
        },
      },
    };

    expect(parseResourceError(err)).toEqual({
      errorCode: 'marketplace.path.invalid',
      message: 'bad path',
      validationResults: [{ code: 'x' }],
    });
  });

  it('reads workspace mcp {error} shape', () => {
    const err = { response: { data: { detail: { error: 'SCOPE_NOT_SUPPORTED', message: 'nope' } } } };
    expect(parseResourceError(err)).toEqual({ errorCode: 'SCOPE_NOT_SUPPORTED', message: 'nope' });
  });

  it('reads skills {code,details} shape', () => {
    const err = {
      response: {
        data: {
          detail: {
            code: 'FILE_CONFLICT',
            message: 'conflict',
            details: { path: '/a' },
          },
        },
      },
    };

    expect(parseResourceError(err)).toEqual({
      errorCode: 'FILE_CONFLICT',
      message: 'conflict',
      validationResults: [{ path: '/a' }],
    });
  });

  it('falls back to Error.message', () => {
    expect(parseResourceError(new Error('boom'))).toEqual({ message: 'boom' });
  });
});

describe('parseResourceResult', () => {
  it('maps legacy marketplace {document} to resource', () => {
    const raw = { revision: 'r1', validationResults: [], document: { id: 'a', path: 'a.md' } };
    expect(parseResourceResult(raw)).toEqual({
      revision: 'r1',
      validationResults: [],
      resource: { id: 'a', path: 'a.md' },
    });
  });

  it('passes through {resource}', () => {
    const raw = { revision: 'r2', resource: { id: 'b' } };
    expect(parseResourceResult(raw)).toEqual({ revision: 'r2', resource: { id: 'b' } });
  });

  it('tolerates missing payload', () => {
    expect(parseResourceResult({ revision: 'r3' })).toEqual({ revision: 'r3' });
  });
});

describe('toResourceList', () => {
  it('flattens workspace grouped scopes and keeps empty available scope', () => {
    const raw = {
      scopes: [
        {
          scope: 'project',
          readOnly: false,
          documents: [{ id: 'project:a', scope: 'project', title: 'a', content: '' }],
        },
        { scope: 'user', readOnly: false, documents: [] },
      ],
    };

    const out = toResourceList(raw);

    expect(out.items.map((d) => d.id)).toEqual(['project:a']);
    expect(out.availableScopes).toEqual([
      { scope: 'project', readOnly: false },
      { scope: 'user', readOnly: false },
    ]);
  });

  it('handles marketplace flat array with no scopes', () => {
    const raw = [{ id: 'x', title: 'x', path: 'x.md', content: '' }];
    const out = toResourceList(raw);
    expect(out.items).toHaveLength(1);
    expect(out.availableScopes).toEqual([]);
  });

  it('keeps backend flat list result with available scopes', () => {
    const raw = {
      items: [{ id: 'user:a', scope: 'user', title: 'a', content: '' }],
      availableScopes: [
        { scope: 'project', readOnly: false },
        { scope: 'user', readOnly: false },
      ],
    };

    expect(toResourceList(raw)).toEqual(raw);
  });
});
