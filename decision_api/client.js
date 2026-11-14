/** Browser/server fetch client. Point it at your app's proxy, never embed an API key. */
export class DecisionAPIError extends Error {
  constructor(message, status = 0) {
    super(message);
    this.name = 'DecisionAPIError';
    this.status = status;
    this.retryable = [0, 502, 503, 504].includes(status);
  }
}

export function createDecisionClient({baseUrl = '/api/decision', fetch: send = globalThis.fetch, timeoutMs = 155000} = {}) {
  const base = baseUrl.replace(/\/$/, '');
  const identifier = value => {
    if (!/^[a-f0-9]{32}$/.test(value)) throw new TypeError('Invalid decision ID');
    return value;
  };
  async function request(path, body, {signal} = {}) {
    const controller = new AbortController();
    const abort = () => controller.abort();
    if (signal?.aborted) abort();
    else signal?.addEventListener('abort', abort, {once: true});
    const timer = setTimeout(abort, timeoutMs);
    try {
      const response = await send(base + path, {
        method: body === undefined ? 'GET' : 'POST',
        headers: body === undefined ? {} : {'Content-Type': 'application/json'},
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: controller.signal,
      });
      let data;
      try { data = await response.json(); }
      catch { throw new DecisionAPIError(`Decision API returned HTTP ${response.status} without JSON`, response.ok ? 502 : response.status); }
      if (!response.ok) throw new DecisionAPIError(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail || data.error || data), response.status);
      return data;
    } catch (error) {
      if (error instanceof DecisionAPIError) throw error;
      if (controller.signal.aborted) throw new DecisionAPIError(signal?.aborted ? 'Request cancelled' : 'The model may still be starting. Retry shortly.', signal?.aborted ? 499 : 0);
      throw new DecisionAPIError('Cannot reach the decision API. No substitute scores were generated.');
    } finally {
      clearTimeout(timer);
      signal?.removeEventListener('abort', abort);
    }
  }
  return {
    // examples() is local: it does not start a GPU. health() is an explicit live call.
    examples: options => request('/examples', undefined, options),
    precomputed: (exampleId, options) => {
      if (!/^(pathway|example-[123])$/.test(exampleId)) throw new TypeError('Unknown saved example');
      return request(`/examples/${exampleId}/decision`, undefined, options);
    },
    health: options => request('/health', undefined, options),
    score: (payload, options) => request('/score', payload, options),
    reason: (payload, options) => request('/reason', payload, options),
    refinePreview: (payload, options) => request('/refine-preview', payload, options),
    propose: (payload, options) => request('/pathway', payload, options),
    scoreExample: (sampleId, payload = {}, options) => {
      if (!/^example-[123]$/.test(sampleId)) throw new TypeError('Unknown photo example');
      return request(`/samples/${sampleId}/score`, payload, options);
    },
    decision: (id, options) => request(`/decisions/${identifier(id)}`, undefined, options),
    review: (id, payload, options) => request(`/decisions/${identifier(id)}/review`, payload, options),
  };
}
