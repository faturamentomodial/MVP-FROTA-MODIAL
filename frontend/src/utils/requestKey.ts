type RequestCrypto = Pick<Crypto, 'getRandomValues'> & Partial<Pick<Crypto, 'randomUUID'>>

/** Idempotency key for a booking, including browsers accessing the app over HTTP. */
export function createRequestKey(provider: RequestCrypto = globalThis.crypto): string {
  if (typeof provider?.randomUUID === 'function') return provider.randomUUID()
  // randomUUID requires a secure context; getRandomValues also works over HTTP.
  if (typeof provider?.getRandomValues !== 'function') {
    throw new Error('Não foi possível preparar a programação. Atualize o navegador e tente novamente.')
  }
  const bytes = provider.getRandomValues(new Uint8Array(16))
  bytes[6] = (bytes[6] & 0x0f) | 0x40
  bytes[8] = (bytes[8] & 0x3f) | 0x80
  const hex = Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('')
  return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`
}
